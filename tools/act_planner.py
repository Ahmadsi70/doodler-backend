"""
Act planner — split long StudioSpecs into contiguous narrative acts.

Why: ~10 min films must not dump every shot into one LLM hop; acts bound
design, context packs, and optional batch render/concat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from studio_spec import ShotControl, StudioSpec


@dataclass
class ActSlice:
    """One contiguous shot range inside a StudioSpec."""

    id: str
    index: int
    title: str
    summary: str
    shot_start: int
    shot_end: int  # exclusive
    duration_sec: float
    token_budget: int = 8000

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "summary": self.summary,
            "shot_start": self.shot_start,
            "shot_end": self.shot_end,
            "duration_sec": self.duration_sec,
            "token_budget": self.token_budget,
        }


@dataclass
class ActPlan:
    """Full film partitioned into acts."""

    acts: list[ActSlice] = field(default_factory=list)
    target_act_seconds: float = 150.0
    runtime_seconds: float = 0.0

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema": "act_plan#v1",
            "target_act_seconds": self.target_act_seconds,
            "runtime_seconds": self.runtime_seconds,
            "acts": [a.to_public_dict() for a in self.acts],
        }


def plan_acts(
    spec: StudioSpec,
    *,
    target_act_seconds: float | None = None,
    token_budget_per_act: int = 8000,
) -> ActPlan:
    """
    Partition shots into acts by cumulative duration.

    Default target ≈ 2.5 min (150s) so a 10 min film yields ~4 acts.
    Always at least one act covering all shots.
    """
    shots = list(spec.shots)
    total = sum(float(s.duration_sec) for s in shots)
    target = float(
        target_act_seconds
        if target_act_seconds is not None
        else min(150.0, max(30.0, float(spec.runtime_seconds) / 3.0))
    )
    if target <= 0:
        target = 150.0

    acts: list[ActSlice] = []
    start = 0
    acc = 0.0
    for i, sh in enumerate(shots):
        acc += float(sh.duration_sec)
        is_last = i == len(shots) - 1
        # Close act when budget hit (and we have at least one shot) or last shot
        should_close = is_last or (acc >= target and i + 1 > start)
        if not should_close:
            continue
        # Avoid tiny leftover act: if remaining after this close is < 25% target,
        # fold remaining into this act (handled by continuing until last).
        remaining_after = sum(float(s.duration_sec) for s in shots[i + 1 :])
        if not is_last and remaining_after < target * 0.25:
            continue
        end = i + 1
        slice_shots = shots[start:end]
        dur = sum(float(s.duration_sec) for s in slice_shots)
        idx = len(acts)
        summary = _act_summary(slice_shots, idx)
        acts.append(
            ActSlice(
                id=f"act-{idx}",
                index=idx,
                title=f"Act {idx + 1}",
                summary=summary,
                shot_start=start,
                shot_end=end,
                duration_sec=dur,
                token_budget=token_budget_per_act,
            )
        )
        start = end
        acc = 0.0

    if not acts:
        acts.append(
            ActSlice(
                id="act-0",
                index=0,
                title="Act 1",
                summary=_act_summary(shots, 0),
                shot_start=0,
                shot_end=len(shots),
                duration_sec=total,
                token_budget=token_budget_per_act,
            )
        )
    return ActPlan(acts=acts, target_act_seconds=target, runtime_seconds=total)


def chunk_spec_by_acts(spec: StudioSpec, plan: ActPlan) -> list[StudioSpec]:
    """Clone one StudioSpec per act with sliced shots (for batch render)."""
    out: list[StudioSpec] = []
    for act in plan.acts:
        slice_shots = list(spec.shots[act.shot_start : act.shot_end])
        if not slice_shots:
            continue
        data = spec.model_dump(mode="json")
        data["title"] = f"{spec.title} — {act.title}"
        data["shots"] = [s.model_dump(mode="json") for s in slice_shots]
        data["runtime_seconds"] = max(1.0, act.duration_sec)
        data["notes"] = f"{spec.notes} act={act.id}".strip()
        out.append(StudioSpec.model_validate(data))
    return out


def _act_summary(shots: list[ShotControl], index: int) -> str:
    if not shots:
        return f"Act {index + 1} (empty)"
    head = shots[0].action[:80]
    tail = shots[-1].action[:80] if len(shots) > 1 else ""
    if tail and tail != head:
        return f"{head} … {tail}"
    return head
