"""
LocomotionCycleAgent — Contact → Down → Passing → Up at 24fps.

Why: PerformanceChart tiles bible samples, but weight reads need explicit
four-beat markers aligned to the action window (and foot contacts).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from tools.pose_presets import joints_for_pose, load_performance_bible
except ImportError:
    from ..tools.pose_presets import joints_for_pose, load_performance_bible  # type: ignore

_FOUR = ("contact", "down", "passing", "up")


def _gait_for(pose: str, beat: str) -> str | None:
    p = (pose or "").lower()
    b = (beat or "").lower()
    if p == "run" or "run" in b:
        return "run"
    if p == "walk" or b in {"entrance", "exit"}:
        return "walk"
    return None


def _cycle_meta(gait: str) -> tuple[int, list[dict[str, Any]]]:
    bible = load_performance_bible()
    row = (bible.get("poses") or {}).get(gait) or {}
    cycle_frames = int(row.get("cycle_frames") or (16 if gait == "run" else 24))
    phases = list(row.get("phases") or [])
    if phases:
        return cycle_frames, phases
    # synthetic four-beat fallback
    j = joints_for_pose(gait, "neutral")
    step = max(1, cycle_frames // 4)
    synth = []
    for i, name in enumerate(_FOUR):
        jj = dict(j)
        if name == "down":
            jj["pelvisY"] = float(jj.get("pelvisY", 0)) - 0.06
        elif name == "up":
            jj["pelvisY"] = float(jj.get("pelvisY", 0)) + 0.05
        synth.append({"frame": i * step, "phase": name, "joints": jj})
    return cycle_frames, synth


def run_locomotion_cycle_agent(
    shots: list[dict[str, Any]],
    *,
    performance_chart: dict[str, Any] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Emit locomotion_cycle#v1: four-beat markers inside each gait shot's action window.
    """
    chart_by = {
        s.get("shot_id"): s for s in (performance_chart or {}).get("shots") or []
    }
    cycles: list[dict[str, Any]] = []
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        chart = chart_by.get(sid) or {}
        pose = str(chart.get("pose") or sh.get("pose") or "idle")
        beat = str(
            chart.get("story_beat")
            or sh.get("story_beat")
            or sh.get("storyBeat")
            or ""
        )
        gait = _gait_for(pose, beat)
        if not gait:
            continue
        dur = int(
            chart.get("duration_frames")
            or sh.get("duration_frames")
            or sh.get("durationFrames")
            or max(12, round(float(sh.get("duration_sec") or 3) * fps))
        )
        ant = int(chart.get("ant_end") or sh.get("anticipation_frames") or 6)
        hold_start = int(
            chart.get("hold_start")
            or max(ant + 1, dur - int(sh.get("hold_frames") or 12))
        )
        cycle_frames, phase_rows = _cycle_meta(gait)
        # Map bible phase frames (0..cycle) into action window by tiling
        beats: list[dict[str, Any]] = []
        foot = "L"
        t = ant
        while t < hold_start:
            for ph in phase_rows:
                name = str(ph.get("phase") or "").lower()
                if name not in _FOUR:
                    continue
                local = int(ph.get("frame") or 0)
                abs_f = t + local
                if abs_f >= hold_start:
                    break
                beat_row = {
                    "frame": abs_f,
                    "phase": name,
                    "foot": foot if name == "contact" else None,
                    "joints": {
                        k: float(v) for k, v in dict(ph.get("joints") or {}).items()
                    },
                }
                beats.append(beat_row)
                if name == "contact":
                    foot = "R" if foot == "L" else "L"
            t += cycle_frames
        # Guarantee at least one full four-beat set
        if not beats:
            step = max(1, min(cycle_frames, hold_start - ant) // 4)
            for i_ph, name in enumerate(_FOUR):
                f = min(hold_start - 1, ant + i_ph * step)
                beats.append(
                    {
                        "frame": f,
                        "phase": name,
                        "foot": "L" if name == "contact" else None,
                        "joints": joints_for_pose(gait, "neutral"),
                    }
                )
        cycles.append(
            {
                "shot_id": sid,
                "gait": gait,
                "cycle_frames": cycle_frames,
                "ant_end": ant,
                "hold_start": hold_start,
                "duration_frames": dur,
                "beats": beats,
                "ms_per_frame": round(1000.0 / fps, 4),
            }
        )
    return {
        "agent": "LocomotionCycleAgent",
        "schema": "locomotion_cycle#v1",
        "fps": fps,
        "cycles": cycles,
        "notes": [f"gait_shots={len(cycles)}"],
    }


def apply_locomotion_to_chart(
    performance_chart: dict[str, Any],
    locomotion: dict[str, Any],
) -> dict[str, Any]:
    """
    Inject four-beat phase keyframes into performance chart (copy, non-destructive input).
    """
    out = deepcopy(performance_chart)
    by_sid = {c.get("shot_id"): c for c in locomotion.get("cycles") or []}
    for shot in out.get("shots") or []:
        cycle = by_sid.get(shot.get("shot_id"))
        if not cycle:
            continue
        kfs = list(shot.get("keyframes") or [])
        by_f: dict[int, dict[str, Any]] = {int(k["frame"]): dict(k) for k in kfs}
        for beat in cycle.get("beats") or []:
            f = int(beat["frame"])
            joints = dict(beat.get("joints") or {})
            if f in by_f and by_f[f].get("joints"):
                # keep denser joints but force phase label
                row = dict(by_f[f])
                row["phase"] = beat["phase"]
                if joints:
                    row["joints"] = {**dict(row.get("joints") or {}), **joints}
                by_f[f] = row
            else:
                by_f[f] = {
                    "frame": f,
                    "phase": beat["phase"],
                    "joints": joints or dict((kfs[0].get("joints") if kfs else {}) or {}),
                }
        shot["keyframes"] = [by_f[f] for f in sorted(by_f)]
        shot["locomotion_gait"] = cycle.get("gait")
        shot["locomotion_beats"] = len(cycle.get("beats") or [])
    out["notes"] = list(out.get("notes") or []) + ["locomotion_enriched=1"]
    return out
