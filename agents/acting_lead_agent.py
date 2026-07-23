"""
ActingLeadAgent — eyes lead head by 2–4 frames (thought before turn).

Why: Williams / timing prompts require eyes-lead; charts previously snapped
expression with the head extreme on the same frame.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from tools.pose_presets import expression_channels
except ImportError:
    from ..tools.pose_presets import expression_channels  # type: ignore


def _lead_frames(pose: str, beat: str) -> int:
    p = (pose or "").lower()
    b = (beat or "").lower()
    if p == "react" or b in {"reaction", "reveal", "conflict"}:
        return 3
    if b in {"decision", "quiet_hold"}:
        return 2
    return 2


def run_acting_lead_agent(
    shots: list[dict[str, Any]],
    *,
    performance_chart: dict[str, Any] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Emit acting_lead#v1 markers: eyes_frame precedes head_frame by 2–4f.
    """
    chart_by = {
        s.get("shot_id"): s for s in (performance_chart or {}).get("shots") or []
    }
    out_shots: list[dict[str, Any]] = []
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        chart = chart_by.get(sid) or {}
        pose = str(chart.get("pose") or sh.get("pose") or "idle")
        expression = str(
            chart.get("expression") or sh.get("expression") or "neutral"
        )
        beat = str(
            chart.get("story_beat")
            or sh.get("story_beat")
            or sh.get("storyBeat")
            or ""
        )
        dur = int(
            chart.get("duration_frames")
            or sh.get("duration_frames")
            or sh.get("durationFrames")
            or 24
        )
        ant = int(chart.get("ant_end") or sh.get("anticipation_frames") or 6)
        lead = _lead_frames(pose, beat)
        # Head hits at extreme / ant_end; eyes earlier
        head_frame = ant
        for k in chart.get("keyframes") or []:
            if str(k.get("phase") or "") in {"extreme", "hit"}:
                head_frame = int(k["frame"])
                break
        eyes_frame = max(0, head_frame - lead)
        channels = expression_channels(expression)
        out_shots.append(
            {
                "shot_id": sid,
                "pose": pose,
                "expression": expression,
                "eyes_lead_frames": lead,
                "eyes_frame": eyes_frame,
                "head_frame": head_frame,
                "duration_frames": dur,
                "channels": channels,
                "ms_per_frame": round(1000.0 / fps, 4),
            }
        )
    return {
        "agent": "ActingLeadAgent",
        "schema": "acting_lead#v1",
        "fps": fps,
        "shots": out_shots,
        "notes": [f"shots={len(out_shots)}"],
    }


def apply_acting_lead_to_chart(
    performance_chart: dict[str, Any],
    acting_lead: dict[str, Any],
) -> dict[str, Any]:
    """
    Attach expression_curve + early eyesOpen key to chart shots (copy).
    """
    out = deepcopy(performance_chart)
    by = {s.get("shot_id"): s for s in acting_lead.get("shots") or []}
    for shot in out.get("shots") or []:
        lead = by.get(shot.get("shot_id"))
        if not lead:
            continue
        ch = dict(lead.get("channels") or {})
        eyes_f = int(lead["eyes_frame"])
        head_f = int(lead["head_frame"])
        dur = int(shot.get("duration_frames") or lead.get("duration_frames") or 24)
        rest_eyes = 1.0
        target_eyes = float(ch.get("eyesOpen") if ch.get("eyesOpen") is not None else 0.9)
        curve = [
            {"frame": 0, "eyesOpen": rest_eyes, "brows": 0.0, "mouth": 0.0},
            {
                "frame": eyes_f,
                "eyesOpen": target_eyes,
                "brows": float(ch.get("brows") or 0),
                "mouth": float(ch.get("mouth") or 0) * 0.4,
            },
            {
                "frame": head_f,
                "eyesOpen": target_eyes,
                "brows": float(ch.get("brows") or 0),
                "mouth": float(ch.get("mouth") or 0),
            },
            {
                "frame": max(0, dur - 1),
                "eyesOpen": target_eyes,
                "brows": float(ch.get("brows") or 0) * 0.7,
                "mouth": float(ch.get("mouth") or 0) * 0.7,
            },
        ]
        shot["expression_curve"] = curve
        # Inject eyes_lead phase keyframe before head extreme
        kfs = list(shot.get("keyframes") or [])
        by_f = {int(k["frame"]): dict(k) for k in kfs}
        if eyes_f not in by_f and kfs:
            base = dict(by_f.get(head_f) or kfs[0])
            joints = dict(base.get("joints") or {})
            # eyes lead: slightly raise headY early as gaze cue
            joints["headY"] = float(joints.get("headY", 0)) + 0.03
            by_f[eyes_f] = {
                "frame": eyes_f,
                "phase": "eyes_lead",
                "joints": joints,
            }
        elif eyes_f in by_f:
            by_f[eyes_f]["phase"] = "eyes_lead"
        shot["keyframes"] = [by_f[f] for f in sorted(by_f)]
        shot["acting_lead_frames"] = lead["eyes_lead_frames"]
    out["notes"] = list(out.get("notes") or []) + ["acting_lead=1"]
    return out


def expression_curve_for_shot(
    acting_lead: dict[str, Any] | None,
    performance_chart: dict[str, Any] | None,
    shot_id: Any,
) -> list[dict[str, Any]] | None:
    """Resolve expression_curve for Remotion shot.expressionCurve."""
    for s in (performance_chart or {}).get("shots") or []:
        if s.get("shot_id") == shot_id and s.get("expression_curve"):
            return list(s["expression_curve"])
    for s in (acting_lead or {}).get("shots") or []:
        if s.get("shot_id") == shot_id:
            # build minimal curve from lead markers
            ch = dict(s.get("channels") or {})
            return [
                {"frame": 0, "eyesOpen": 1.0, "brows": 0.0, "mouth": 0.0},
                {
                    "frame": int(s["eyes_frame"]),
                    "eyesOpen": float(ch.get("eyesOpen") or 0.9),
                    "brows": float(ch.get("brows") or 0),
                    "mouth": float(ch.get("mouth") or 0) * 0.4,
                },
                {
                    "frame": int(s["head_frame"]),
                    "eyesOpen": float(ch.get("eyesOpen") or 0.9),
                    "brows": float(ch.get("brows") or 0),
                    "mouth": float(ch.get("mouth") or 0),
                },
            ]
    return None
