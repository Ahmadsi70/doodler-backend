"""
Frame supervision gate — fail-closed checks on performance chart density.

Why: StorySupervisor scored brief/pack text; film quality needs fps-level
evidence (keyframes + walk four-beats + contact lock) before Approve/render.
"""

from __future__ import annotations

import os
from typing import Any

_FOUR = frozenset({"contact", "down", "passing", "up"})


def frame_gate_strict(*, extras: dict[str, Any] | None = None) -> bool:
    """True when FRAME_GATE_STRICT=1 or extras.frame_gate_strict."""
    if extras and extras.get("frame_gate_strict") is not None:
        return bool(extras.get("frame_gate_strict"))
    return os.environ.get("FRAME_GATE_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _min_keyframes(dur: int) -> int:
    # At least one sample ~every 12f, floor 4 for short shots
    return max(4, dur // 12)


def run_frame_gate(
    artifacts: dict[str, Any],
    *,
    strict: bool | None = None,
) -> dict[str, Any]:
    """
    Evaluate frame-level supervision on props-like artifacts.

    Expects keys: performanceChart, contactLock (optional), locomotionCycles (optional).
    """
    findings: list[str] = []
    chart = artifacts.get("performanceChart") or {}
    contacts = list((artifacts.get("contactLock") or {}).get("contacts") or [])
    loco_cycles = {
        c.get("shot_id"): c for c in (artifacts.get("locomotionCycles") or {}).get("cycles") or []
    }
    shots = list(chart.get("shots") or [])
    if not shots:
        findings.append("frame:missing_performance_chart")
    for sh in shots:
        sid = sh.get("shot_id")
        dur = int(sh.get("duration_frames") or 0)
        kfs = list(sh.get("keyframes") or [])
        need = _min_keyframes(dur) if dur else 4
        if len(kfs) < need:
            findings.append(f"frame:sparse_keyframes:shot{sid}:have={len(kfs)}:need>={need}")
        pose = str(sh.get("pose") or sh.get("locomotion_gait") or "").lower()
        gait = pose in {"walk", "run"} or sid in loco_cycles
        if gait:
            phases = {str(k.get("phase") or "").lower() for k in kfs}
            if loco_cycles.get(sid):
                phases |= {
                    str(b.get("phase") or "").lower()
                    for b in (loco_cycles[sid].get("beats") or [])
                }
            missing = _FOUR - phases
            if missing:
                findings.append(
                    f"frame:walk_four_beats_missing:shot{sid}:{','.join(sorted(missing))}"
                )
            feet = [
                c
                for c in contacts
                if c.get("shot_id") == sid and str(c.get("kind", "")).startswith("foot")
            ]
            if not feet:
                findings.append(f"frame:missing_foot_contacts:shot{sid}")

    passed = len(findings) == 0
    report = {
        "agent": "FrameGate",
        "schema": "frame_gate#v1",
        "passed": passed,
        "score": 1.0 if passed else max(0.0, 1.0 - 0.15 * len(findings)),
        "findings": findings[:24],
        "shots_checked": len(shots),
    }
    use_strict = frame_gate_strict() if strict is None else strict
    if use_strict and not passed:
        raise RuntimeError(
            f"FrameGate FAIL findings={report['findings'][:6]}"
        )
    return report
