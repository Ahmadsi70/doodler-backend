"""
Style catalog helpers — Midlibrary-inspired taxonomy + starter pack.

Loads ``libraries/styles/*`` and resolves studio-default / requested styles
into engine-ready bindings (camera, grade, pace, motion alias).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from libraries import load_library
    from tools.studio_profiles import normalize_kind
    from tools.studio_router import pack_for_studio
except ImportError:
    from ..libraries import load_library
    from .studio_profiles import normalize_kind
    from .studio_router import pack_for_studio

# Map endcard preset keys → seconds for FFmpeg post
ENDCARD_SECONDS: dict[str, float] = {
    "logo_last_5s": 5.0,
    "soft_fade": 2.0,
    "soft_brand_tag": 4.0,
}


@lru_cache(maxsize=8)
def _starter_pack() -> dict[str, Any]:
    return load_library("styles", "starter_pack.json")


@lru_cache(maxsize=4)
def _studio_map() -> dict[str, Any]:
    return load_library("styles", "studio_style_map.json")


@lru_cache(maxsize=4)
def _bindings() -> dict[str, Any]:
    return load_library("styles", "engine_bindings.json")


@lru_cache(maxsize=4)
def _features() -> dict[str, Any]:
    return load_library("styles", "features.json")


@lru_cache(maxsize=4)
def _categories() -> dict[str, Any]:
    return load_library("styles", "categories.json")


def clear_style_cache() -> None:
    _starter_pack.cache_clear()
    _studio_map.cache_clear()
    _bindings.cache_clear()
    _features.cache_clear()
    _categories.cache_clear()


def list_styles() -> list[dict[str, Any]]:
    return list(_starter_pack().get("styles") or [])


def get_style(style_id: str) -> dict[str, Any] | None:
    for style in list_styles():
        if style.get("style_id") == style_id:
            return style
    return None


def styles_for_studio(studio: str | None = None) -> list[dict[str, Any]]:
    """Story-only: recommended + studio_fit containing studio_story."""
    kind = normalize_kind(studio)
    recommended = (_studio_map().get("recommended_style_ids") or {}).get(kind) or []
    by_id = {s["style_id"]: s for s in list_styles()}
    out = [by_id[i] for i in recommended if i in by_id]
    seen = {s["style_id"] for s in out}
    for style in list_styles():
        fit = style.get("studio_fit") or []
        if kind in fit and style["style_id"] not in seen:
            out.append(style)
            seen.add(style["style_id"])
    return out


def default_style_id(studio: str | None = None) -> str:
    kind = normalize_kind(studio)
    defaults = _studio_map().get("default_style_by_studio") or {}
    return str(defaults.get(kind) or "symmetrical_pastel_cinema")


def resolve_style(
    style_id: str | None = None,
    *,
    studio: str | None = None,
) -> dict[str, Any]:
    """Resolve a style; falls back to Story default when unknown."""
    kind = normalize_kind(studio)
    sid = style_id or default_style_id(kind)
    style = get_style(sid) or get_style(default_style_id(kind))
    allowed = {s["style_id"] for s in styles_for_studio(kind)}
    if style is None or (allowed and sid not in allowed and style_id):
        fallback = get_style(default_style_id(kind))
        style = fallback or style
    if style is None:
        raise KeyError(f"No style available for studio={kind}")

    engine = dict(style.get("engine") or {})
    binds = _bindings()
    camera_key = engine.get("camera")
    grade_key = engine.get("grade")
    pace_key = engine.get("pace")
    endcard_key = engine.get("endcard")
    motion_alias = engine.get("motion_alias")

    motion_map = binds.get("motion_style_aliases") or {}
    resolved_motion = None
    if motion_alias:
        resolved_motion = motion_map.get(motion_alias, motion_alias)

    return {
        "style_id": style["style_id"],
        "name": style.get("name"),
        "category": style.get("category"),
        "features": list(style.get("features") or []),
        "studio_kind": kind,
        "craft_pack": pack_for_studio(kind),
        "prompt_traits": list(style.get("prompt_traits") or []),
        "quality_hooks": list(style.get("quality_hooks") or []),
        "camera": (binds.get("camera_presets") or {}).get(camera_key, {}),
        "camera_preset": camera_key,
        "grade": (binds.get("grade_presets") or {}).get(grade_key, {}),
        "grade_preset": grade_key,
        "pace": (binds.get("pace_presets") or {}).get(pace_key, {}),
        "pace_preset": pace_key,
        "endcard": (binds.get("endcard_presets") or {}).get(endcard_key, {}),
        "endcard_preset": endcard_key,
        "motion_alias": motion_alias,
        "motion_style": resolved_motion,
    }


def taxonomy_summary() -> dict[str, Any]:
    feats = _features()
    cats = _categories()
    return {
        "category_count": len(cats.get("categories") or []),
        "feature_group_count": len(feats.get("groups") or {}),
        "feature_count": sum(len(v) for v in (feats.get("groups") or {}).values()),
        "starter_count": len(list_styles()),
        "video_priority_features": list(feats.get("video_priority_features") or []),
    }


def endcard_seconds_for(resolved: dict[str, Any] | None) -> float:
    if not resolved:
        return 2.5
    key = str(resolved.get("endcard_preset") or "")
    return float(ENDCARD_SECONDS.get(key, 2.5))


def write_style_profile(job_dir: Path | str, resolved: dict[str, Any]) -> Path:
    """Persist resolved style + executable Stage-1 runtime bindings."""
    try:
        from tools.style_runtime import enrich_style_profile_file
    except ImportError:
        from .style_runtime import enrich_style_profile_file

    payload = dict(resolved)
    payload["endcard_seconds"] = endcard_seconds_for(resolved)
    # enrich writes camera_spec + grade_vf into style_profile.json
    out = Path(job_dir) / "style_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return enrich_style_profile_file(job_dir, payload)


def merge_style_into_extras(
    extras: dict[str, Any] | None,
    studio: str,
) -> dict[str, Any]:
    """
    Resolve ``style_id`` for the studio and inject engine fields into extras.

    - Sets ``style_id``, ``style_resolved``
    - Fills ``motion_style`` from style alias when missing (Motion/Education)
    """
    merged = dict(extras or {})
    kind = normalize_kind(studio)
    resolved = resolve_style(merged.get("style_id"), studio=kind)
    merged["style_id"] = resolved["style_id"]
    merged["style_resolved"] = resolved
    if resolved.get("motion_style") and not merged.get("motion_style"):
        merged["motion_style"] = resolved["motion_style"]
    return merged


def ui_style_options(studio: str) -> list[tuple[str, str]]:
    """Return ``(style_id, label)`` pairs for Streamlit selectboxes."""
    kind = normalize_kind(studio)
    default = default_style_id(kind)
    rows = styles_for_studio(kind)
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for style in rows:
        sid = str(style["style_id"])
        if sid in seen:
            continue
        seen.add(sid)
        label = f"{style.get('name')} ({sid})"
        options.append((sid, label))
    # Ensure default is first
    options.sort(key=lambda pair: (0 if pair[0] == default else 1, pair[1].lower()))
    return options
