"""StorySupervisor — Story-only oversight for 2D narrative."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from scene_ir import AuditorVerdict, SceneIR, empty_scene_ir
except ImportError:
    from ..scene_ir import AuditorVerdict, SceneIR, empty_scene_ir  # type: ignore

try:
    from prompts import load_prompt
except ImportError:
    from ..prompts import load_prompt  # type: ignore

try:
    from tools.pack_quality_gate import (
        quality_gate_strict,
        run_pack_quality_gate,
        write_pack_quality_gate,
    )
except ImportError:
    from ..tools.pack_quality_gate import (  # type: ignore
        quality_gate_strict,
        run_pack_quality_gate,
        write_pack_quality_gate,
    )

STORY_SUPERVISOR_ID = "StorySupervisor"
STORY_PACK = "story"
STORY_STUDIO = "studio_story"
REPORT_NAME = "story_supervisor.json"

_TARGET_BOARD = "StoryboardAgent"
_TARGET_TIMING = "AnimationTimingAgent"
_TARGET_CONTINUITY = "ContinuityAgent"


@dataclass
class StorySupervisorReport:
    auditor_id: str = STORY_SUPERVISOR_ID
    pack: str = STORY_PACK
    studio: str = STORY_STUDIO
    passed: bool = False
    score: float = 0.0
    findings: list[str] = field(default_factory=list)
    revision_target: str | None = None
    notes: str = ""
    craft: dict[str, Any] = field(default_factory=dict)
    pack_gate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_auditor_verdict(self) -> AuditorVerdict:
        return AuditorVerdict(
            auditor_id=self.auditor_id,
            passed=self.passed,
            score=float(max(0.0, min(1.0, self.score))),
            revision_target=self.revision_target,
            findings=list(self.findings)[:16],
            notes=self.notes,
        )


def _beat_count(brief: str) -> int:
    parts = [p.strip() for p in re.split(r"\n\s*\n+", brief or "") if p.strip()]
    if len(parts) >= 2:
        return len(parts)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", brief or "") if s.strip()]
    return max(1, len(sentences)) if (brief or "").strip() else 0


def evaluate_story_craft(
    brief: str, *, extras: dict[str, Any] | None = None
) -> dict[str, Any]:
    extras = dict(extras or {})
    findings: list[str] = []
    scores: list[float] = []
    revision: str | None = None
    text = (brief or "").strip()
    if not text:
        return {
            "ok": False,
            "score": 0.0,
            "findings": ["brief_empty: Story brief required"],
            "revision_target": _TARGET_BOARD,
            "shots": 0,
        }
    shots = _beat_count(text)
    if shots >= 3:
        scores.append(1.0)
    elif shots == 2:
        scores.append(0.75)
        findings.append("shots_soft: prefer ≥3 narrative beats")
    else:
        scores.append(0.35)
        findings.append("shots_low: need ≥2 blank-line beats")
        revision = _TARGET_BOARD
    blob = text.lower()
    if any(k in blob for k in ("then", "because", "until", "بعد", "چون", "تا اینکه")):
        scores.append(1.0)
    else:
        scores.append(0.55)
        findings.append("causality_soft: show cause before effect")
        revision = revision or _TARGET_BOARD
    has_character = bool(
        extras.get("character_main")
        or extras.get("character_path")
        or "character" in blob
        or "شخصیت" in blob
    )
    if has_character:
        scores.append(1.0)
    else:
        scores.append(0.5)
        findings.append("character_soft: provide main character photo or name")
    craft_score = sum(scores) / max(1, len(scores))
    ok = craft_score >= 0.45 and bool(text) and shots >= 2
    return {
        "ok": ok,
        "score": round(craft_score, 3),
        "findings": findings,
        "revision_target": revision if not ok else None,
        "shots": shots,
        "has_character_signal": has_character,
    }


def evaluate_continuity_craft(continuity: dict[str, Any] | None) -> dict[str, Any]:
    """Score ContinuityAgent output for supervisor merge."""
    if not continuity:
        return {
            "ok": True,
            "score": 0.7,
            "findings": ["continuity_soft: no continuity payload"],
            "revision_target": None,
        }
    findings: list[str] = []
    violations = list(continuity.get("violations") or [])
    approved = bool(continuity.get("approved", not violations))
    checks = continuity.get("checks") or []
    flips = sum(
        1
        for i in range(1, len(checks))
        if (checks[i] or {}).get("screen_direction")
        != (checks[i - 1] or {}).get("screen_direction")
    )
    if violations:
        findings.append(f"continuity_violations: {len(violations)}")
    if flips > 1:
        findings.append(f"screen_direction_flips: {flips}")
        approved = False
    score = 1.0 if approved and not violations else (0.55 if flips <= 1 else 0.3)
    return {
        "ok": approved and score >= 0.45,
        "score": round(score, 3),
        "findings": findings,
        "revision_target": _TARGET_CONTINUITY if not approved else None,
        "approved": approved,
        "violations": violations,
        "screen_direction_flips": flips,
        "180_line_side": continuity.get("180_line_side"),
    }


def run_story_supervisor(
    scene: SceneIR | None = None,
    *,
    brief: str | None = None,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    job_dir: Path | str | None = None,
    strict: bool | None = None,
    continuity: dict[str, Any] | None = None,
) -> StorySupervisorReport:
    extras = dict(extras or {})
    if continuity is not None:
        extras["continuity"] = continuity
    elif job_dir:
        cont_path = Path(job_dir) / "agents" / "continuity.json"
        if cont_path.is_file():
            try:
                extras["continuity"] = json.loads(
                    cont_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                pass
    os.environ["RENDER_STUDIO"] = STORY_STUDIO
    if scene is None:
        scene = empty_scene_ir(brief or "")
    prompt = brief if brief is not None else (scene.user_prompt or "")
    craft = evaluate_story_craft(prompt, extras=extras)
    cont_craft = evaluate_continuity_craft(extras.get("continuity"))
    craft = {
        **craft,
        "continuity": cont_craft,
        "score": round(
            0.7 * float(craft["score"]) + 0.3 * float(cont_craft["score"]), 3
        ),
        "ok": bool(craft["ok"]) and bool(cont_craft["ok"]),
        "findings": list(craft.get("findings") or [])
        + list(cont_craft.get("findings") or []),
        "revision_target": craft.get("revision_target")
        or cont_craft.get("revision_target"),
    }
    gate = run_pack_quality_gate(
        scene,
        studio=STORY_STUDIO,
        extras=extras,
        style_profile=style_profile,
    )
    findings = list(craft.get("findings") or [])
    for c in gate.checks:
        if c.status == "fail":
            findings.append(f"pack:{c.check_id}:{c.detail}")
    score = round(0.45 * float(craft["score"]) + 0.55 * float(gate.score), 3)
    passed = bool(craft["ok"]) and bool(gate.passed)
    revision = None
    if not passed:
        revision = craft.get("revision_target") or _TARGET_BOARD
        if cont_craft.get("revision_target") and not cont_craft.get("ok"):
            revision = _TARGET_CONTINUITY
        elif gate.passed is False and craft.get("ok"):
            revision = _TARGET_TIMING
    # Optional frame-level gate when performance chart is in extras
    frame_report: dict[str, Any] | None = None
    if isinstance(extras.get("performanceChart"), dict) or isinstance(
        extras.get("performance_chart"), dict
    ):
        try:
            from tools.frame_gate import run_frame_gate
        except ImportError:
            findings.append("frame_gate:skip:import")
        else:
            try:
                frame_report = run_frame_gate(
                    {
                        "performanceChart": extras.get("performanceChart")
                        or extras.get("performance_chart"),
                        "contactLock": extras.get("contactLock")
                        or extras.get("contact_lock"),
                        "locomotionCycles": extras.get("locomotionCycles")
                        or extras.get("locomotion_cycles"),
                    },
                    strict=False,
                )
                findings.extend(list(frame_report.get("findings") or [])[:8])
                if not frame_report.get("passed"):
                    passed = False
                    score = round(min(score, float(frame_report.get("score") or 0.4)), 3)
                    revision = revision or _TARGET_TIMING
            except Exception as exc:  # noqa: BLE001
                findings.append(f"frame_gate:error:{type(exc).__name__}")
                frame_report = None
    report = StorySupervisorReport(
        passed=passed,
        score=score,
        findings=findings[:20],
        revision_target=revision,
        notes=(
            f"StorySupervisor craft={craft['score']} pack={gate.score} "
            f"shots={craft.get('shots')}"
            + (
                f" frame={frame_report.get('score')}"
                if frame_report
                else ""
            )
        ),
        craft=craft,
        pack_gate=gate.to_dict(),
    )
    out = job_dir or scene.job_out_dir
    if out:
        path = Path(out) / REPORT_NAME
        path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        write_pack_quality_gate(out, gate)
    use_strict = quality_gate_strict(extras=extras) if strict is None else strict
    if use_strict and not report.passed:
        raise RuntimeError(
            f"StorySupervisor FAIL score={report.score} findings={report.findings[:6]}"
        )
    return report
