"""
PerformanceChartAgent — dense 24fps pose charts per shot.

Why: shot-level ant/hold ints are not enough for ms-level supervision;
Remotion must consume extremes → breakdowns → holds as keyframes.
"""

from __future__ import annotations

from typing import Any

try:
    from tools.pose_presets import expression_channels, joints_for_pose, load_performance_bible
except ImportError:
    from ..tools.pose_presets import (  # type: ignore
        expression_channels,
        joints_for_pose,
        load_performance_bible,
    )


def _lerp_joints(a: dict[str, float], b: dict[str, float], u: float) -> dict[str, float]:
    keys = set(a) | set(b)
    return {k: float(a.get(k, 0.0)) + (float(b.get(k, 0.0)) - float(a.get(k, 0.0))) * u for k in keys}


def _scale_joints(j: dict[str, float], scale: float) -> dict[str, float]:
    out = dict(j)
    for k in ("pelvisY", "headY", "leftLegStride", "rightLegStride", "leftArmSwing", "rightArmSwing"):
        if k in out:
            out[k] = float(out[k]) * scale
    return out


_BEAT_TO_EXPRESSION: dict[str, str] = {
    "entrance": "worry",
    "reveal": "shock",
    "reaction": "shock",
    "decision": "happy",
    "conflict": "angry",
    "exit": "happy",
    "quiet_hold": "neutral",
    "celebration": "happy",
    "sneak": "worry",
    "triumph": "happy",
}


def _bible_cycle(pose: str, expression: str) -> list[dict[str, Any]]:
    bible = load_performance_bible()
    pose_row = (bible.get("poses") or {}).get((pose or "idle").lower())
    bias = (
        ((bible.get("expressions") or {}).get((expression or "neutral").lower()) or {}).get(
            "joint_bias"
        )
        or {}
    )
    if pose_row and pose_row.get("phases"):
        out = []
        for ph in pose_row["phases"]:
            joints = {k: float(v) for k, v in dict(ph.get("joints") or {}).items()}
            for k, v in bias.items():
                joints[k] = float(joints.get(k, 0.0)) + float(v)
            out.append(
                {
                    "frame": int(ph.get("frame") or 0),
                    "phase": str(ph.get("phase") or pose),
                    "joints": joints,
                }
            )
        return out
    # fallback two keys
    j = joints_for_pose(pose, expression)
    return [
        {"frame": 0, "phase": "start", "joints": _scale_joints(j, 0.4)},
        {"frame": 12, "phase": pose, "joints": j},
    ]


def _expand_cycle_into_range(
    cycle: list[dict[str, Any]],
    *,
    start: int,
    end: int,
    cycle_len: int,
) -> list[dict[str, Any]]:
    """Tile bible cycle across [start, end)."""
    if end <= start or not cycle:
        return []
    # normalize cycle to 0..cycle_len
    base = sorted(cycle, key=lambda x: int(x["frame"]))
    span = max(1, cycle_len)
    keys: list[dict[str, Any]] = []
    t = start
    while t < end:
        local = (t - start) % span
        # find surrounding phase keys
        a = base[0]
        b = base[-1]
        for i in range(len(base) - 1):
            if int(base[i]["frame"]) <= local <= int(base[i + 1]["frame"]):
                a, b = base[i], base[i + 1]
                break
        fa, fb = int(a["frame"]), int(b["frame"])
        u = 0.0 if fb <= fa else (local - fa) / (fb - fa)
        joints = _lerp_joints(a["joints"], b["joints"], u)
        phase = str(a.get("phase") or "cycle")
        # emit on phase boundaries or every 6 frames for density
        if local in {int(p["frame"]) for p in base} or (t - start) % 6 == 0 or t == start:
            keys.append({"frame": t, "phase": phase, "joints": joints})
        t += 1
    # ensure last action frame sampled
    if keys and keys[-1]["frame"] < end - 1:
        local = (end - 1 - start) % span
        a = base[0]
        b = base[-1]
        for i in range(len(base) - 1):
            if int(base[i]["frame"]) <= local <= int(base[i + 1]["frame"]):
                a, b = base[i], base[i + 1]
                break
        fa, fb = int(a["frame"]), int(b["frame"])
        u = 0.0 if fb <= fa else (local - fa) / (fb - fa)
        keys.append(
            {
                "frame": end - 1,
                "phase": str(b.get("phase") or "cycle"),
                "joints": _lerp_joints(a["joints"], b["joints"], u),
            }
        )
    # dedupe frames
    by_f: dict[int, dict[str, Any]] = {}
    for k in keys:
        by_f[int(k["frame"])] = k
    return [by_f[f] for f in sorted(by_f)]


def _chart_one_shot(sh: dict[str, Any], *, fps: int) -> dict[str, Any]:
    dur = int(sh.get("duration_frames") or max(12, round(float(sh.get("duration_sec") or 3) * fps)))
    ant = max(0, min(int(sh.get("anticipation_frames") or 6), max(0, dur - 2)))
    hold = max(0, min(int(sh.get("hold_frames") or 12), max(0, dur - ant - 1)))
    hold_start = dur - hold
    ant_end = ant
    pose = str(sh.get("pose") or "idle")
    beat = str(sh.get("story_beat") or sh.get("storyBeat") or "decision")
    expression = str(sh.get("expression")) if sh.get("expression") else _BEAT_TO_EXPRESSION.get(beat, "neutral")

    rest = joints_for_pose("idle", expression)
    peak = joints_for_pose(pose, expression)
    cycle = _bible_cycle(pose, expression)
    cycle_len = max(
        12,
        int((load_performance_bible().get("poses") or {}).get(pose, {}).get("cycle_frames") or 24),
    )

    keyframes: list[dict[str, Any]] = []

    # Anticipation: settle → squash toward peak inverse
    if ant_end > 0:
        keyframes.append({"frame": 0, "phase": "anticipation", "joints": rest})
        squash = _scale_joints(peak, 0.55)
        squash["pelvisY"] = float(squash.get("pelvisY", 0)) - 0.08
        keyframes.append(
            {
                "frame": max(0, ant_end - 1),
                "phase": "anticipation",
                "joints": squash,
            }
        )

    # Action: tiled cycle or extreme hit
    if pose == "react":
        # anticipation already set; extreme at ant_end, settle into hold
        keyframes.append({"frame": ant_end, "phase": "extreme", "joints": peak})
        mid = ant_end + max(1, (hold_start - ant_end) // 2)
        if mid < hold_start:
            keyframes.append(
                {
                    "frame": mid,
                    "phase": "hit",
                    "joints": _scale_joints(peak, 0.9),
                }
            )
        if hold_start - 1 > ant_end:
            keyframes.append(
                {
                    "frame": hold_start - 1,
                    "phase": "settle",
                    "joints": _scale_joints(peak, 0.75),
                }
            )
    else:
        action_keys = _expand_cycle_into_range(
            cycle, start=ant_end, end=hold_start, cycle_len=cycle_len
        )
        if not action_keys and ant_end < hold_start:
            action_keys = [
                {"frame": ant_end, "phase": "action", "joints": peak},
                {
                    "frame": max(ant_end, hold_start - 1),
                    "phase": "action",
                    "joints": peak,
                },
            ]
        keyframes.extend(action_keys)

    # Hold / aftermath
    if hold > 0:
        hold_pose = _scale_joints(peak, 0.85 if pose == "react" else 1.0)
        keyframes.append({"frame": hold_start, "phase": "hold", "joints": hold_pose})
        if dur - 1 > hold_start:
            # micro breath
            breath = dict(hold_pose)
            breath["pelvisY"] = float(breath.get("pelvisY", 0)) + 0.02
            breath["headY"] = float(breath.get("headY", 0)) + 0.01
            keyframes.append({"frame": dur - 1, "phase": "hold", "joints": breath})

    # Deduplicate / sort / clamp
    by_f: dict[int, dict[str, Any]] = {}
    for k in keyframes:
        f = max(0, min(dur - 1, int(k["frame"])))
        by_f[f] = {
            "frame": f,
            "phase": str(k.get("phase") or ""),
            "joints": {kk: float(vv) for kk, vv in dict(k.get("joints") or {}).items()},
        }
    ordered = [by_f[f] for f in sorted(by_f)]

    return {
        "shot_id": sh.get("shot_id", sh.get("shotId")),
        "pose": pose,
        "expression": expression,
        "story_beat": beat,
        "duration_frames": dur,
        "anticipation_frames": ant,
        "hold_frames": hold,
        "ant_end": ant_end,
        "hold_start": hold_start,
        "keyframes": ordered,
        "expression_channels": expression_channels(expression),
        "ms_per_frame": round(1000.0 / fps, 4),
    }


def run_performance_chart_agent(
    shots: list[dict[str, Any]],
    *,
    fps: int = 24,
) -> dict[str, Any]:
    """Build performance_chart#v1 for all shots."""
    chart_shots = [_chart_one_shot(sh, fps=fps) for sh in shots]
    total = sum(int(s["duration_frames"]) for s in chart_shots)
    return {
        "agent": "PerformanceChartAgent",
        "schema": "performance_chart#v1",
        "fps": fps,
        "shots": chart_shots,
        "total_frames": total,
        "notes": [
            f"shots={len(chart_shots)}",
            f"keyframes={sum(len(s['keyframes']) for s in chart_shots)}",
        ],
    }


def chart_shot_to_rig(shot_chart: dict[str, Any], *, fps: int = 24) -> dict[str, Any]:
    """Convert one chart shot → Remotion shotRig payload."""
    return {
        "fps": fps,
        "totalFrames": int(shot_chart.get("duration_frames") or fps),
        "keyframes": list(shot_chart.get("keyframes") or []),
        "expression": shot_chart.get("expression_channels")
        or expression_channels(str(shot_chart.get("expression") or "neutral")),
        "pose": shot_chart.get("pose"),
        "performance_id": f"chart:{shot_chart.get('pose')}",
        "williams_character": False,
        "source": "PerformanceChartAgent",
    }
