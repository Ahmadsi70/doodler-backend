"""
Pose / expression presets for Remotion CharacterRig.

Why: craftHints.rig.pose must change joints on screen via Performance Bible,
not stay as unused labels.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_BIBLE = _ROOT / "libraries" / "performance" / "bible.json"


@lru_cache(maxsize=1)
def load_performance_bible() -> dict[str, Any]:
    """Load executable performance bible (poses + expressions)."""
    if not _BIBLE.is_file():
        return {"poses": {}, "expressions": {}, "fps": 24}
    return json.loads(_BIBLE.read_text(encoding="utf-8"))


def _fallback_joints(pose: str) -> dict[str, float]:
    p = (pose or "idle").lower().strip()
    base = {
        "pelvisY": 0.0,
        "hipsRotZ": 0.0,
        "shouldersRotZ": 0.0,
        "leftLegStride": 0.0,
        "rightLegStride": 0.0,
        "leftKneeBend": 0.12,
        "rightKneeBend": 0.12,
        "leftArmSwing": 0.0,
        "rightArmSwing": 0.0,
        "headY": 0.0,
        "beltTiltDeg": 0.0,
        "shoulderTiltDeg": 0.0,
    }
    if p == "walk":
        base.update(
            {
                "pelvisY": 0.08,
                "hipsRotZ": 6.0,
                "shouldersRotZ": -8.0,
                "leftLegStride": 0.55,
                "rightLegStride": -0.45,
                "leftKneeBend": 0.35,
                "rightKneeBend": 0.22,
                "leftArmSwing": -0.5,
                "rightArmSwing": 0.55,
                "headY": 0.04,
                "beltTiltDeg": 3.0,
            }
        )
    elif p == "react":
        base.update(
            {
                "pelvisY": -0.18,
                "hipsRotZ": -4.0,
                "shouldersRotZ": 14.0,
                "leftLegStride": -0.15,
                "rightLegStride": 0.2,
                "leftKneeBend": 0.45,
                "rightKneeBend": 0.4,
                "leftArmSwing": 0.35,
                "rightArmSwing": -0.4,
                "headY": 0.22,
                "shoulderTiltDeg": 8.0,
                "beltTiltDeg": -4.0,
            }
        )
    elif p in {"run", "scramble"}:
        base.update(
            {
                "pelvisY": 0.15,
                "hipsRotZ": 10.0,
                "shouldersRotZ": -12.0,
                "leftLegStride": 0.85,
                "rightLegStride": -0.8,
                "leftKneeBend": 0.55,
                "rightKneeBend": 0.5,
                "leftArmSwing": -0.85,
                "rightArmSwing": 0.9,
                "headY": 0.1,
            }
        )
    return base


def joints_for_pose(pose: str, expression: str = "neutral") -> dict[str, float]:
    """Return joint channels for a craft pose label (peak / mid-cycle)."""
    p = (pose or "idle").lower().strip()
    e = (expression or "neutral").lower().strip()
    bible = load_performance_bible()
    pose_row = (bible.get("poses") or {}).get(p) or (bible.get("poses") or {}).get("idle")
    if pose_row and pose_row.get("phases"):
        phases = list(pose_row["phases"])
        mid = phases[len(phases) // 2]
        base = {k: float(v) for k, v in dict(mid.get("joints") or {}).items()}
    else:
        base = _fallback_joints(p)

    expr = (bible.get("expressions") or {}).get(e) or {}
    bias = expr.get("joint_bias") or {}
    for k, v in bias.items():
        base[k] = float(base.get(k, 0.0)) + float(v)
    # Legacy expression offsets when bible lacks joint_bias
    if not bias:
        if e == "shock":
            base["headY"] = float(base.get("headY", 0)) + 0.12
            base["shouldersRotZ"] = float(base.get("shouldersRotZ", 0)) + 4.0
            base["pelvisY"] = float(base.get("pelvisY", 0)) - 0.06
        elif e == "hope":
            base["headY"] = float(base.get("headY", 0)) + 0.06
            base["shouldersRotZ"] = float(base.get("shouldersRotZ", 0)) - 2.0
        elif e == "worry":
            base["headY"] = float(base.get("headY", 0)) - 0.04
            base["beltTiltDeg"] = float(base.get("beltTiltDeg", 0)) - 2.0
    return base


def expression_channels(expression: str) -> dict[str, float | str]:
    """Face channels for CharacterRig.expression."""
    e = (expression or "neutral").lower().strip()
    bible = load_performance_bible()
    row = (bible.get("expressions") or {}).get(e)
    if row:
        out = {k: v for k, v in row.items() if k != "joint_bias"}
        return out
    table = {
        "neutral": {
            "emotion": "neutral",
            "brows": 0.0,
            "mouth": 0.0,
            "eyesOpen": 1.0,
            "faceSy": 0.0,
        },
        "shock": {
            "emotion": "shock",
            "brows": 0.85,
            "mouth": 0.7,
            "eyesOpen": 0.35,
            "faceSy": 0.1,
        },
        "hope": {
            "emotion": "hope",
            "brows": -0.2,
            "mouth": 0.35,
            "eyesOpen": 1.0,
            "faceSy": 0.0,
        },
        "worry": {
            "emotion": "worry",
            "brows": 0.45,
            "mouth": -0.25,
            "eyesOpen": 0.75,
            "faceSy": -0.05,
        },
        "happy": {
            "emotion": "happy",
            "brows": -0.35,
            "mouth": 0.6,
            "eyesOpen": 0.85,
            "faceSy": 0.15,
        },
        "angry": {
            "emotion": "angry",
            "brows": -0.7,
            "mouth": -0.4,
            "eyesOpen": 0.7,
            "faceSy": -0.1,
        },
    }
    return dict(table.get(e) or table["neutral"])


def bake_shot_rig(
    *,
    pose: str,
    expression: str,
    base_rig: dict[str, Any] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Build a keyframed rig for one shot from Performance Bible phases.
    """
    p = (pose or "idle").lower().strip()
    expr = expression_channels(expression)
    bible = load_performance_bible()
    pose_row = (bible.get("poses") or {}).get(p)
    base = dict(base_rig or {})
    base_kfs = list(base.get("keyframes") or [])

    if pose_row and pose_row.get("phases"):
        kfs = []
        for ph in pose_row["phases"]:
            joints = {k: float(v) for k, v in dict(ph.get("joints") or {}).items()}
            # Apply expression joint bias onto each phase
            bias = ((bible.get("expressions") or {}).get((expression or "neutral").lower()) or {}).get(
                "joint_bias"
            ) or {}
            for k, v in bias.items():
                joints[k] = float(joints.get(k, 0.0)) + float(v)
            kfs.append(
                {
                    "frame": int(ph.get("frame") or 0),
                    "phase": str(ph.get("phase") or p),
                    "joints": joints,
                }
            )
        total = int(pose_row.get("cycle_frames") or kfs[-1]["frame"] or fps)
        return {
            "fps": fps,
            "totalFrames": max(12, total),
            "keyframes": kfs,
            "expression": expr,
            "pose": p,
            "performance_id": str(pose_row.get("id") or p),
            "williams_character": bool(base.get("williams_character")),
        }

    if base_kfs and p == "walk":
        return {
            **base,
            "expression": {**(base.get("expression") or {}), **expr},
            "pose": p,
            "performance_id": "walk",
            "williams_character": bool(base.get("williams_character")),
        }

    joints = joints_for_pose(p, expression)
    kfs = [
        {
            "frame": 0,
            "phase": p,
            "joints": {**joints, "leftLegStride": joints["leftLegStride"] * 0.4},
        },
        {
            "frame": max(8, fps // 2),
            "phase": p,
            "joints": joints,
        },
    ]
    return {
        "fps": fps,
        "totalFrames": max(12, fps),
        "keyframes": kfs,
        "expression": expr,
        "pose": p,
        "performance_id": p,
        "williams_character": bool(base.get("williams_character")),
    }


def env_profile_for_beat(beat: str, lighting: str | None = None) -> dict[str, Any]:
    """Environment layer recipe for a narrative beat."""
    b = (beat or "decision").lower()
    moods = {
        "entrance": "soft",
        "reveal": "soft",
        "reaction": "tense",
        "conflict": "drama",
        "decision": "neutral",
        "quiet_hold": "soft",
        "exit": "exit",
    }
    mood = moods.get(b, "neutral")
    haze = 0.22 if mood in {"soft", "exit"} else (0.35 if mood == "tense" else 0.18)
    shaft = mood in {"reveal", "reaction", "soft"}
    ground = 0.55 if mood != "exit" else 0.35
    # Optional look bible vignette
    vignette = 0.4 if mood in {"tense", "drama", "exit"} else 0.25
    try:
        from tools.craft_packs import load_look_bible

        look = load_look_bible()
        grade_id = (look.get("beat_grade") or {}).get(b)
        grade = (look.get("grades") or {}).get(grade_id or "") or {}
        if grade.get("vignette") is not None:
            vignette = float(grade["vignette"])
        parallax = float(grade.get("parallax") or (0.7 if mood in {"tense", "drama"} else 0.5))
        depth_layers = int(grade.get("depth_layers") or 3)
    except Exception:  # noqa: BLE001
        parallax = 0.7 if mood in {"tense", "drama"} else 0.5
        depth_layers = 3
    return {
        "mood": mood,
        "haze": haze,
        "lightShaft": shaft,
        "groundStrength": ground,
        "vignette": vignette,
        "horizonY": 0.62 if mood != "exit" else 0.7,
        "lighting": lighting or "three_point",
        "parallax": parallax,
        "depthLayers": depth_layers,
    }
