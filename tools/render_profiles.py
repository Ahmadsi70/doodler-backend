"""Fixed render profiles — Story tool only (2D Light / Remotion Pro)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

UNIVERSAL_FPS = 24
QualityMode = Literal["light", "pro"]
STORY_STUDIO = "studio_story"


@dataclass(frozen=True)
class RenderProfile:
    studio: str
    quality: str
    width: int
    height: int
    fps: int
    backend: str
    manim_q: str
    seconds_per_slide: float
    prefer_manim_when_pro: bool
    default_motion_style: str | None = None
    notes: str = ""
    blender_engine: str = ""
    storyboard_engine: str = ""

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["resolution"] = [self.width, self.height]
        return d


def _p(
    quality: str,
    *,
    width: int,
    height: int,
    backend: str,
    seconds_per_slide: float = 3.0,
    notes: str = "",
) -> RenderProfile:
    return RenderProfile(
        studio=STORY_STUDIO,
        quality=quality,
        width=width,
        height=height,
        fps=UNIVERSAL_FPS,
        backend=backend,
        manim_q="l",
        seconds_per_slide=seconds_per_slide,
        prefer_manim_when_pro=False,
        default_motion_style="story",
        notes=notes,
    )


RENDER_PROFILES: dict[tuple[str, str], RenderProfile] = {
    (STORY_STUDIO, "light"): _p(
        "light",
        width=1280,
        height=720,
        backend="light_slideshow",
        seconds_per_slide=3.0,
        notes="Storyboard draft via FFmpeg slideshow",
    ),
    (STORY_STUDIO, "pro"): _p(
        "pro",
        width=1920,
        height=1080,
        backend="remotion",
        seconds_per_slide=3.5,
        notes="Remotion local 2D cutout narrative @ 1080p24",
    ),
}


def normalize_quality(quality: str | None) -> QualityMode:
    return "pro" if str(quality or "light").lower() == "pro" else "light"


def get_render_profile(
    studio: str | None = None,
    quality: str | None = "light",
) -> RenderProfile:
    q = normalize_quality(quality)
    return RENDER_PROFILES[(STORY_STUDIO, q)]


def write_render_profile(
    out_dir: Path | str,
    profile: RenderProfile,
    *,
    extra: dict[str, Any] | None = None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = profile.to_dict()
    if extra:
        payload["extra"] = extra
    path = out / "render_profile.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def all_profile_keys() -> list[tuple[str, str]]:
    return sorted(RENDER_PROFILES.keys())
