"""
Professional storybook delivery profile (1080p24).

Why: page films stay light on RAM; Ken Burns encode streams without Remotion.
"""

from __future__ import annotations

from typing import Any

PRO_WIDTH = 1920
PRO_HEIGHT = 1080
PRO_FPS = 24
PRO_WRITE_FRAME_PNGS = False
PRO_TARGET_SEC_7MIN = 420.0


def frames_for_duration(duration_sec: float, *, fps: int = PRO_FPS) -> int:
    """Whole frames for a timed segment (fail-closed positive)."""
    return max(1, int(round(float(duration_sec) * float(max(1, int(fps))))))


def extrapolate_wall_sec(
    *,
    sample_sec: float,
    wall_sec: float,
    target_sec: float,
) -> float:
    """Linear wall-time scale from a timed sample to a longer cut."""
    s = float(sample_sec)
    if s <= 0.0:
        raise ValueError("sample_sec must be > 0")
    return float(wall_sec) * (float(target_sec) / s)


def pro_profile_dict() -> dict[str, Any]:
    """Stable knobs for CLI / reports."""
    return {
        "tier": "professional",
        "width": PRO_WIDTH,
        "height": PRO_HEIGHT,
        "fps": PRO_FPS,
        "write_frame_pngs": PRO_WRITE_FRAME_PNGS,
        "engine": "storybook",
        "notes": "1080p24 storybook Ken Burns + crossfade; no cutouts",
    }
