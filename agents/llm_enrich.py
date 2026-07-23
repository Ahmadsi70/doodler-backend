"""Optional LLM enrichment for Story agent chain (storyboard → cine → timing → continuity)."""

from __future__ import annotations

import os
from typing import Any

try:
    from llm.deepseek_client import AGENT_TEMPERATURES, chat_json, deepseek_configured
except ImportError:
    from ..llm.deepseek_client import (  # type: ignore
        AGENT_TEMPERATURES,
        chat_json,
        deepseek_configured,
    )

try:
    from tools.studio_router import compose_system_prompt
except ImportError:
    from ..tools.studio_router import compose_system_prompt  # type: ignore


def llm_enabled(extras: dict[str, Any] | None = None) -> bool:
    extras = extras or {}
    flag = extras.get("use_llm")
    if flag is False:
        return False
    if flag is True:
        return deepseek_configured()
    env = (os.environ.get("STORY_USE_LLM") or "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    if env in {"1", "true", "yes", "on"}:
        return deepseek_configured()
    return deepseek_configured()


def validate_storyboard_shots(shots: Any) -> list[dict[str, Any]] | None:
    """Hard schema gate before merging LLM storyboard output."""
    if not isinstance(shots, list) or not shots:
        return None
    out: list[dict[str, Any]] = []
    for row in shots:
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "").strip()
        if not action:
            continue
        try:
            duration = float(row.get("duration_sec") or 3.0)
        except (TypeError, ValueError):
            duration = 3.0
        if duration <= 0 or duration > 120:
            continue
        out.append(
            {
                "shot_id": row.get("shot_id"),
                "title": str(row.get("title") or "")[:80],
                "action": action[:400],
                "duration_sec": duration,
                "idea": str(row.get("idea") or action)[:120],
            }
        )
    return out or None


def validate_timing_shots(shots: Any, *, fps: int = 24) -> list[dict[str, Any]] | None:
    """Require anticipation/hold floors for LLM timing rows."""
    if not isinstance(shots, list) or not shots:
        return None
    out: list[dict[str, Any]] = []
    for row in shots:
        if not isinstance(row, dict):
            continue
        try:
            sec = float(row.get("duration_sec") or 3.0)
            hold = int(row.get("hold_frames") or 12)
            ant = int(row.get("anticipation_frames") or 6)
        except (TypeError, ValueError):
            continue
        if sec <= 0:
            continue
        out.append(
            {
                "shot_id": row.get("shot_id"),
                "duration_sec": sec,
                "duration_frames": max(12, int(round(sec * fps))),
                "hold_frames": max(8, hold),
                "anticipation_frames": max(4, ant),
            }
        )
    return out or None


def validate_cine_frames(frames: Any) -> list[dict[str, Any]] | None:
    if not isinstance(frames, list) or not frames:
        return None
    allowed_cam = {"static", "motivated_push"}
    allowed_lens = {"standard", "action", "beauty"}
    out: list[dict[str, Any]] = []
    for row in frames:
        if not isinstance(row, dict):
            continue
        cam = str(row.get("camera") or "static")
        lens = str(row.get("lens") or "standard")
        if cam not in allowed_cam or lens not in allowed_lens:
            continue
        out.append(
            {
                "shot_id": row.get("shot_id"),
                "lens": lens,
                "composition": str(row.get("composition") or "C")[:1],
                "camera": cam,
                "lighting": str(row.get("lighting") or "three_point"),
            }
        )
    return out or None


def enrich_storyboard_llm(
    brief: str,
    storyboard: dict[str, Any],
    *,
    context_block: str | None = None,
) -> dict[str, Any] | None:
    if not deepseek_configured():
        return None
    fallback = (
        "You are StoryboardAgent. One clear idea per shot. Cause before effect. "
        "Short action lines. Use only the CONTEXT pack shots when provided."
    )
    invocation = (
        "Return JSON with key shots: array of "
        "{shot_id, title, action, duration_sec, idea}."
    )
    system = compose_system_prompt(
        "narrative", invocation, studio="studio_story", fallback=fallback
    )
    ctx = f"\n\nCONTEXT PACK:\n{context_block}" if context_block else ""
    data = chat_json(
        role="narrative",
        system=system,
        user=f"Brief:\n{brief}{ctx}\n\nCurrent shots:\n{storyboard.get('shots')}",
        temperature=AGENT_TEMPERATURES.get("narrative", 0.85),
    )
    if not data:
        return None
    validated = validate_storyboard_shots(data.get("shots"))
    if not validated:
        return None
    base = {s.get("shot_id"): s for s in (storyboard.get("shots") or [])}
    merged = []
    for row in validated:
        sid = row.get("shot_id")
        prev = base.get(sid) or {}
        merged.append(
            {
                "shot_id": sid if sid is not None else prev.get("shot_id"),
                "title": str(row.get("title") or prev.get("title") or "")[:80],
                "action": str(row.get("action") or prev.get("action") or "")[:400],
                "duration_sec": float(
                    row.get("duration_sec")
                    if row.get("duration_sec") is not None
                    else prev.get("duration_sec")
                    or 3.0
                ),
                "idea": str(row.get("idea") or prev.get("idea") or "")[:120],
            }
        )
    if not merged:
        return None
    out = dict(storyboard)
    out["shots"] = merged
    out["llm_enriched"] = True
    out["llm_validated"] = True
    return out


def enrich_cinematography_llm(
    brief: str,
    cinematography: dict[str, Any],
    storyboard: dict[str, Any],
) -> dict[str, Any] | None:
    if not deepseek_configured():
        return None
    fallback = (
        "You are CinematographyAgent. Assign lens, composition (L|C|R), "
        "camera (static|motivated_push), lighting per shot."
    )
    invocation = (
        "Return JSON with key frames: array of "
        "{shot_id, lens, composition, camera, lighting}."
    )
    system = compose_system_prompt(
        "cinematography", invocation, studio="studio_story", fallback=fallback
    )
    data = chat_json(
        role="cinematography",
        system=system,
        user=(
            f"Brief:\n{brief}\n\nShots:\n{storyboard.get('shots')}\n\n"
            f"Current frames:\n{cinematography.get('frames')}"
        ),
        temperature=AGENT_TEMPERATURES.get("cinematography", 0.35),
    )
    validated = validate_cine_frames(data.get("frames") if data else None)
    if not validated:
        return None
    out = dict(cinematography)
    out["frames"] = validated
    out["llm_enriched"] = True
    out["llm_validated"] = True
    return out


def enrich_timing_llm(
    brief: str,
    timing: dict[str, Any],
    storyboard: dict[str, Any],
) -> dict[str, Any] | None:
    if not deepseek_configured():
        return None
    fallback = (
        "You are AnimationTimingAgent. Keep 24fps. Set duration_sec, "
        "hold_frames (>=12), anticipation_frames (>=4) per shot."
    )
    invocation = (
        "Return JSON with key shots: array of "
        "{shot_id, duration_sec, hold_frames, anticipation_frames}."
    )
    system = compose_system_prompt(
        "timing", invocation, studio="studio_story", fallback=fallback
    )
    data = chat_json(
        role="timing",
        system=system,
        user=(
            f"Brief:\n{brief}\n\nStoryboard:\n{storyboard.get('shots')}\n\n"
            f"Current timing:\n{timing.get('shots')}"
        ),
        temperature=AGENT_TEMPERATURES.get("timing", 0.20),
    )
    fps = int(timing.get("fps") or 24)
    validated = validate_timing_shots(data.get("shots") if data else None, fps=fps)
    if not validated:
        return None
    base = {s.get("shot_id"): s for s in (timing.get("shots") or [])}
    merged = []
    for row in validated:
        sid = row.get("shot_id")
        prev = base.get(sid) or {}
        merged.append(
            {
                **{k: v for k, v in prev.items() if k.startswith("williams_")},
                "shot_id": sid if sid is not None else prev.get("shot_id"),
                "duration_sec": row["duration_sec"],
                "duration_frames": row["duration_frames"],
                "hold_frames": row["hold_frames"],
                "anticipation_frames": row["anticipation_frames"],
            }
        )
    if not merged:
        return None
    out = dict(timing)
    out["shots"] = merged
    out["llm_enriched"] = True
    out["llm_validated"] = True
    return out


def enrich_continuity_llm(
    brief: str,
    continuity: dict[str, Any],
    storyboard: dict[str, Any],
    cinematography: dict[str, Any],
) -> dict[str, Any] | None:
    if not deepseek_configured():
        return None
    fallback = (
        "You are ContinuityAgent. Keep 180-degree line. Flag screen-direction "
        "and eyeline violations. Cause before effect."
    )
    invocation = (
        "Return JSON with keys: 180_line_side, eyeline_map, cut_notes, "
        "violations, approved, checks "
        "(array of {shot_id, screen_direction, eyeline, cause_before_effect})."
    )
    system = compose_system_prompt(
        "continuity", invocation, studio="studio_story", fallback=fallback
    )
    data = chat_json(
        role="auditor",
        system=system,
        user=(
            f"Brief:\n{brief}\n\nShots:\n{storyboard.get('shots')}\n\n"
            f"Cine:\n{cinematography.get('frames')}\n\n"
            f"Current continuity:\n{continuity}"
        ),
        temperature=AGENT_TEMPERATURES.get("auditor", 0.0),
    )
    if not data or not isinstance(data, dict):
        return None
    out = dict(continuity)
    for key in (
        "180_line_side",
        "eyeline_map",
        "cut_notes",
        "violations",
        "approved",
        "checks",
    ):
        if key in data:
            out[key] = data[key]
    out["llm_enriched"] = True
    out["system_prompt_loaded"] = True
    return out
