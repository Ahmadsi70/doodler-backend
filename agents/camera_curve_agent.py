"""
CameraCurveAgent — per-shot camera keyframes (scale / tx / ty + ease).

Why: Remotion linear interpolate on cameraMove endpoints looks mechanical;
curved ease + ant/hold anchors give film-readable push/pan/reveal.
"""

from __future__ import annotations

from typing import Any


def _ease_for_move(move_id: str) -> str:
    mid = (move_id or "static").lower()
    if mid in {"motivated_push", "push"}:
        return "ease_in_out"
    if mid in {"pan_follow", "pan"}:
        return "ease_out"
    if mid in {"reveal_drift", "reveal"}:
        return "ease_in"
    return "linear"


def _curve_one(sh: dict[str, Any], *, fps: int) -> dict[str, Any]:
    sid = sh.get("shot_id", sh.get("shotId", 0))
    dur = int(
        sh.get("duration_frames")
        or sh.get("durationFrames")
        or max(12, round(float(sh.get("duration_sec") or sh.get("durationSec") or 3) * fps))
    )
    ant = max(0, min(int(sh.get("anticipation_frames") or sh.get("anticipationFrames") or 6), dur - 2))
    hold = max(0, min(int(sh.get("hold_frames") or sh.get("holdFrames") or 12), max(0, dur - ant - 1)))
    hold_start = dur - hold

    move = sh.get("camera_move") or sh.get("cameraMove") or {}
    if not isinstance(move, dict):
        move = {}
    move_id = str(move.get("id") or sh.get("camera") or "static")
    scale_end = float(move.get("scale_end") if move.get("scale_end") is not None else 1.0)
    tx_end = float(move.get("translate_x") if move.get("translate_x") is not None else 0.0)
    ty_end = float(move.get("translate_y") if move.get("translate_y") is not None else 0.0)
    ease = _ease_for_move(move_id)

    # Static: tiny breath hold curve (near-identity)
    if move_id in {"static", ""} and scale_end == 1.0 and tx_end == 0.0 and ty_end == 0.0:
        keyframes = [
            {"frame": 0, "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": "hold"},
            {"frame": max(0, dur - 1), "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": "hold"},
        ]
    elif move_id in {"motivated_push", "push"} or scale_end > 1.02:
        # Hold framing through anticipation, push during action, settle in hold
        keyframes = [
            {"frame": 0, "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": "hold"},
            {"frame": ant, "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": ease},
            {
                "frame": max(ant + 1, hold_start),
                "scale": scale_end,
                "tx": tx_end * 0.85,
                "ty": ty_end * 0.85,
                "ease": "ease_out",
            },
            {
                "frame": max(0, dur - 1),
                "scale": scale_end,
                "tx": tx_end,
                "ty": ty_end,
                "ease": "hold",
            },
        ]
    else:
        # pan / reveal: start after ant, finish by hold_start
        keyframes = [
            {"frame": 0, "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": "hold"},
            {"frame": ant, "scale": 1.0, "tx": 0.0, "ty": 0.0, "ease": ease},
            {
                "frame": max(ant + 1, hold_start),
                "scale": scale_end,
                "tx": tx_end,
                "ty": ty_end,
                "ease": "ease_out",
            },
            {
                "frame": max(0, dur - 1),
                "scale": scale_end,
                "tx": tx_end,
                "ty": ty_end,
                "ease": "hold",
            },
        ]

    # Deduplicate frames (keep last)
    by_f: dict[int, dict[str, Any]] = {}
    for k in keyframes:
        by_f[int(k["frame"])] = k
    ordered = [by_f[f] for f in sorted(by_f)]
    return {
        "shot_id": sid,
        "move_id": move_id,
        "duration_frames": dur,
        "keyframes": ordered,
        "ms_per_frame": round(1000.0 / fps, 4),
    }


def run_camera_curve_agent(
    shots: list[dict[str, Any]],
    *,
    fps: int = 24,
) -> dict[str, Any]:
    """Build camera_curve#v1 for all shots."""
    curves = [_curve_one(sh, fps=fps) for sh in shots]
    return {
        "agent": "CameraCurveAgent",
        "schema": "camera_curve#v1",
        "fps": fps,
        "shots": curves,
        "notes": [f"shots={len(curves)}"],
    }


def curve_for_shot(camera_curves: dict[str, Any] | None, shot_id: Any) -> dict[str, Any] | None:
    """Lookup one shot's curve payload for Remotion ``cameraCurve`` field."""
    if not camera_curves:
        return None
    for s in camera_curves.get("shots") or []:
        if s.get("shot_id") == shot_id:
            return {
                "move_id": s.get("move_id"),
                "keyframes": list(s.get("keyframes") or []),
            }
    return None
