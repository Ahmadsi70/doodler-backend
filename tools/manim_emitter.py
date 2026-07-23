"""Manim is disabled in Story — use Remotion Pro or Light FFmpeg."""

from __future__ import annotations

from typing import Any


def _disabled(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "Story has no Manim path. Use quality=pro (Remotion) or quality=light."
    )


render_commercial = _disabled
render_story_manim = _disabled
launch_manim_render = _disabled


def manim_quality_flag(*_args: Any, **_kwargs: Any) -> str:
    raise RuntimeError("Manim disabled in Story")
