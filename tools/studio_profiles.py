"""Story — quality modes and backend routing (standalone 2D)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Literal

STORY_STUDIO = "studio_story"
StudioKind = Literal["studio_story"]
QualityMode = Literal["light", "pro"]


def normalize_kind(kind: str | None = None) -> str:
    return STORY_STUDIO


def requires_blender(kind: str | None = None) -> bool:
    return False


def requires_manim(kind: str | None = None) -> bool:
    return False


def requires_remotion(kind: str | None = None) -> bool:
    return True


def quality_resolution(
    mode: QualityMode | str,
    *,
    studio: str | None = None,
) -> tuple[int, int]:
    try:
        from tools.render_profiles import get_render_profile
    except ImportError:
        from .render_profiles import get_render_profile

    return get_render_profile(STORY_STUDIO, mode).resolution


def find_ffmpeg() -> str | None:
    env = (os.environ.get("FFMPEG_PATH") or "").strip()
    if env and os.path.isfile(env):
        return env
    return shutil.which("ffmpeg")


def find_node() -> str | None:
    return shutil.which("node")


def find_npm() -> str | None:
    return shutil.which("npm")


def find_remotion() -> bool:
    """True when Remotion project deps are installed under remotion/."""
    root = Path(__file__).resolve().parents[1] / "remotion" / "node_modules" / "remotion"
    return root.is_dir()


def studio_labels() -> list[tuple[str, str]]:
    return [("Story / Narrative", STORY_STUDIO)]


def readiness_for_kind(
    probe: dict[str, Any], kind: str | None = None
) -> tuple[bool, list[str]]:
    """Export-only studio — no in-tool render backends required."""
    _ = probe, kind
    return True, []
