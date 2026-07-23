"""
Bridge Williams Character/Walk engines → Remotion ``characterRig`` props.

Non-fatal: returns a minimal idle rig when Node/Williams unavailable.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "remotion" / "scripts" / "enrich_character.mjs"

_IDLE: dict[str, Any] = {
    "ok": True,
    "fps": 24,
    "totalFrames": 24,
    "williams_character": False,
    "expression": {
        "emotion": "neutral",
        "brows": 0,
        "mouth": 0,
        "eyesOpen": 1,
        "faceSy": 0,
    },
    "keyframes": [
        {
            "frame": 0,
            "phase": "contact",
            "joints": {
                "pelvisY": 0,
                "hipsRotZ": 0,
                "shouldersRotZ": 0,
                "leftLegStride": 0.2,
                "rightLegStride": -0.2,
                "leftKneeBend": 0.1,
                "rightKneeBend": 0.1,
                "leftArmSwing": -0.15,
                "rightArmSwing": 0.15,
                "headY": 0,
                "beltTiltDeg": 0,
                "shoulderTiltDeg": 0,
            },
        },
        {
            "frame": 12,
            "phase": "passing",
            "joints": {
                "pelvisY": 0.02,
                "hipsRotZ": 4,
                "shouldersRotZ": -4,
                "leftLegStride": -0.15,
                "rightLegStride": 0.15,
                "leftKneeBend": 0.25,
                "rightKneeBend": 0.2,
                "leftArmSwing": 0.2,
                "rightArmSwing": -0.2,
                "headY": 0.01,
                "beltTiltDeg": 2,
                "shoulderTiltDeg": -2,
            },
        },
    ],
}


def enrich_character_rig(
    *,
    emotion: str = "neutral",
    steps: int = 2,
    job_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Return characterRig dict (keyframes + expression) for Remotion."""
    if not _SCRIPT.is_file():
        return dict(_IDLE)
    node = __import__("shutil").which("node")
    if not node:
        return dict(_IDLE)
    payload = json.dumps({"emotion": emotion, "steps": steps})
    try:
        proc = subprocess.run(
            [node, str(_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(_ROOT / "remotion"),
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return dict(_IDLE)
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return dict(_IDLE)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return dict(_IDLE)
    if not isinstance(data, dict) or not data.get("keyframes"):
        return dict(_IDLE)
    if job_dir:
        out = Path(job_dir) / "williams_character.json"
        out.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return data
