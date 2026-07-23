"""
ContactLockAgent — foot / impact contact frames for physics + Foley lock.

Why: Audio and weight reads must attach to contact frames (±1), not arbitrary
quarter-shot offsets — enables ~41.7ms supervision at 24fps.
"""

from __future__ import annotations

from typing import Any


def run_contact_lock_agent(
    shots: list[dict[str, Any]],
    *,
    performance_chart: dict[str, Any] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Emit contact_lock#v1 markers (local + global frame).

    Kinds: foot_L / foot_R / impact / landing (mapped to SceneIR-friendly labels).
    """
    chart_by = {}
    for s in (performance_chart or {}).get("shots") or []:
        chart_by[s.get("shot_id")] = s

    contacts: list[dict[str, Any]] = []
    cursor = 0
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        chart = chart_by.get(sid) or {}
        dur = int(
            chart.get("duration_frames")
            or sh.get("duration_frames")
            or max(12, round(float(sh.get("duration_sec") or 3) * fps))
        )
        ant = int(chart.get("ant_end") or sh.get("anticipation_frames") or 6)
        hold_start = int(chart.get("hold_start") or max(ant + 1, dur - int(sh.get("hold_frames") or 12)))
        pose = str(chart.get("pose") or sh.get("pose") or "idle").lower()
        beat = str(chart.get("story_beat") or sh.get("story_beat") or sh.get("storyBeat") or "")
        action = str(sh.get("action") or "").lower()

        def _add(local: int, kind: str, label: str) -> None:
            f = max(0, min(dur - 1, int(local)))
            contacts.append(
                {
                    "id": f"c-{sid}-{kind}-{f}",
                    "shot_id": sid,
                    "frame": f,
                    "global_frame": cursor + f,
                    "shot_duration_frames": dur,
                    "subject_id": "main",
                    "kind": kind,
                    "label": label,
                    "ir_kind": (
                        "footstep"
                        if kind.startswith("foot")
                        else ("landing" if kind == "landing" else "impact")
                    ),
                }
            )

        # Walk / entrance / exit: alternating foot contacts in action window
        if pose in {"walk", "run"} or beat in {"entrance", "exit"}:
            step = 8 if pose == "run" else 12
            t = ant
            foot = "L"
            while t < hold_start:
                _add(t, f"foot_{foot}", f"{foot} contact")
                foot = "R" if foot == "L" else "L"
                t += step
            if not any(c["shot_id"] == sid and c["kind"].startswith("foot") for c in contacts):
                _add(min(ant + 2, dur - 1), "foot_L", "L contact")

        # React / conflict / hit language → impact at extreme (ant_end)
        if pose == "react" or beat in {"reaction", "conflict"} or any(
            w in action for w in ("shock", "hit", "impact", "fight", "burn", "slam")
        ):
            _add(ant, "impact", "impact extreme")

        # Landing cue
        if "land" in pose or "land" in action:
            _add(ant, "landing", "landing")

        cursor += dur

    return {
        "agent": "ContactLockAgent",
        "schema": "contact_lock#v1",
        "fps": fps,
        "contacts": contacts,
        "notes": [f"contacts={len(contacts)}", f"shots={len(shots)}"],
    }
