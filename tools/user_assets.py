"""Path A — Story user assets: character + slides."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _existing(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    p = Path(str(path))
    if p.is_file():
        return p.resolve()
    return None


def collect_slide_images(extras: dict[str, Any] | None) -> list[Path]:
    extras = extras or {}
    raw = extras.get("slide_images") or extras.get("slide_image") or []
    if isinstance(raw, (str, Path)):
        raw = [raw]
    out: list[Path] = []
    for item in raw:
        p = _existing(item)
        if p is not None:
            out.append(p)
    return out


def normalize_user_assets(extras: dict[str, Any] | None) -> dict[str, Any]:
    extras = dict(extras or {})
    character = extras.get("character_main") or extras.get("character_path")
    slides = extras.get("slide_images") or []
    if isinstance(slides, (str, Path)):
        slides = [str(slides)]
    else:
        slides = [str(s) for s in slides if s]
    return {
        "character_main": str(character) if character else None,
        "slide_images": slides,
    }
