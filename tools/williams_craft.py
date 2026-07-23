"""
Williams craft pack loader + applicator.

Why: NotebookLM distill under ``libraries/williams`` must drive Remotion timing
fields (anticipation/hold) and cine camera/lens — not sit as unused JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from libraries import load_library
except ImportError:
    from ..libraries import load_library  # type: ignore

STUDIO = "williams"
MIN_BEHAVIOR_CONFIDENCE = 0.7

_BEAT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("entrance", ("enter", "enters", "arrive", "arrives", "opens", "وارد")),
    ("exit", ("exit", "leave", "leaves", "depart", "خارج", "می‌رود", "ميرود")),
    ("reaction", ("shock", "react", "reaction", "surprised", "gasp", "شوک", "متعجب")),
    ("reveal", ("reveal", "discover", "finds", "sees", "uncover", "کشف", "پیدا")),
    ("decision", ("decide", "chooses", "resolve", "تصمیم")),
    ("conflict", ("fight", "conflict", "clash", "against", "درگیر")),
    ("quiet_hold", ("quiet", "still", "pause", "breathe", "hold", "آرام", "سکوت")),
)


@dataclass
class WilliamsCraftPack:
    """Loaded ``libraries/williams`` Information Points."""

    fps: int = 24
    principles: list[dict[str, Any]] = field(default_factory=list)
    timing_recipes: list[dict[str, Any]] = field(default_factory=list)
    shot_behaviors: list[dict[str, Any]] = field(default_factory=list)
    anti_patterns: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def load_williams_craft_pack() -> WilliamsCraftPack:
    """Load and normalize the Williams craft Module Node from disk."""
    meta = load_library(STUDIO, "meta.json")
    principles_raw = load_library(STUDIO, "principles.json")
    recipes_raw = load_library(STUDIO, "timing_recipes.json")
    behaviors_raw = load_library(STUDIO, "shot_behaviors.json")
    anti_raw = load_library(STUDIO, "anti_patterns.json")

    principles = (
        principles_raw
        if isinstance(principles_raw, list)
        else list(principles_raw.get("principles") or [])
    )
    recipes = (
        recipes_raw.get("recipes")
        if isinstance(recipes_raw, dict)
        else list(recipes_raw or [])
    )
    behaviors = (
        behaviors_raw
        if isinstance(behaviors_raw, list)
        else list(behaviors_raw.get("shot_behaviors") or [])
    )
    antis = (
        anti_raw
        if isinstance(anti_raw, list)
        else list(anti_raw.get("anti_patterns") or [])
    )
    fps = int(
        (recipes_raw.get("fps") if isinstance(recipes_raw, dict) else None)
        or meta.get("fps")
        or 24
    )
    return WilliamsCraftPack(
        fps=fps,
        principles=list(principles),
        timing_recipes=list(recipes or []),
        shot_behaviors=list(behaviors),
        anti_patterns=list(antis),
        meta=dict(meta) if isinstance(meta, dict) else {},
    )


def infer_story_beat(
    action: str,
    *,
    index: int,
    total: int,
) -> str:
    """Map shot text/position → Williams story_beat id."""
    text = (action or "").lower()
    for beat, keys in _BEAT_KEYWORDS:
        if any(k in text for k in keys):
            return beat
    if total <= 1:
        return "quiet_hold"
    if index == 0:
        return "entrance"
    if index >= total - 1:
        return "exit"
    if index == 1 and total >= 3:
        return "reaction"
    return "decision"


def behavior_for_beat(
    pack: WilliamsCraftPack, beat: str
) -> dict[str, Any] | None:
    """Pick highest-confidence shot_behavior for a story beat."""
    candidates = [
        b
        for b in pack.shot_behaviors
        if str(b.get("story_beat") or "") == beat
        and float(b.get("confidence") or 0) >= MIN_BEHAVIOR_CONFIDENCE
    ]
    if not candidates:
        candidates = [
            b
            for b in pack.shot_behaviors
            if str(b.get("story_beat") or "") == beat
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda b: float(b.get("confidence") or 0))


# Back-compat alias for older imports/tests.
_behavior_for_beat = behavior_for_beat


def apply_williams_craft(
    storyboard: dict[str, Any],
    timing: dict[str, Any],
    cinematography: dict[str, Any],
    *,
    pack: WilliamsCraftPack | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """
    Enrich timing + cinematography from shot_behaviors.

    Returns (timing, cinematography, notes). Mutates copies, not callers' refs
    unless the caller reassigns the returned dicts.
    """
    pack = pack or load_williams_craft_pack()
    notes: list[str] = []
    shots = list(storyboard.get("shots") or [])
    timing_out = dict(timing)
    timing_shots = [dict(s) for s in (timing.get("shots") or [])]
    by_id = {s.get("shot_id"): s for s in timing_shots}

    cine_out = dict(cinematography)
    frames = [dict(f) for f in (cinematography.get("frames") or [])]
    frame_by_id = {f.get("shot_id"): f for f in frames}

    applied = 0
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id")
        action = str(sh.get("action") or sh.get("idea") or "")
        beat = infer_story_beat(action, index=i, total=len(shots))
        behavior = behavior_for_beat(pack, beat)
        if not behavior:
            continue
        row = by_id.get(sid)
        if row is None:
            continue
        t = behavior.get("timing") or {}
        ant = int(t.get("anticipationFrames") or t.get("anticipation_frames") or 0)
        hold = int(t.get("holdFrames") or t.get("hold_frames") or 0)
        if ant > 0:
            row["anticipation_frames"] = ant
        if hold > 0:
            row["hold_frames"] = hold
        bias = t.get("actionBias") or t.get("action_bias")
        if bias:
            row["action_bias"] = bias
        row["williams_behavior_id"] = behavior.get("id")
        row["williams_story_beat"] = beat
        rig = behavior.get("rig") or {}
        if rig:
            row["williams_rig"] = dict(rig)

        fr = frame_by_id.get(sid)
        if fr is not None:
            if behavior.get("camera"):
                fr["camera"] = behavior["camera"]
            if behavior.get("lens"):
                fr["lens"] = behavior["lens"]
            fr["williams_behavior_id"] = behavior.get("id")
        applied += 1

    timing_out["shots"] = timing_shots
    timing_out["fps"] = int(timing_out.get("fps") or pack.fps)
    timing_out["williams_craft_applied"] = applied > 0
    timing_out["williams_craft_version"] = str(
        (pack.meta or {}).get("version") or "1.0.0"
    )
    cine_out["frames"] = frames
    if applied:
        notes.append(f"williams_craft=applied:{applied}")
    else:
        notes.append("williams_craft=skip")
    return timing_out, cine_out, notes


def recipe_maps_by_id(pack: WilliamsCraftPack | None = None) -> dict[str, dict[str, int]]:
    """Index timing recipe ``maps_to_project_fields`` by recipe id."""
    pack = pack or load_williams_craft_pack()
    out: dict[str, dict[str, int]] = {}
    for recipe in pack.timing_recipes:
        rid = str(recipe.get("id") or "")
        maps = recipe.get("maps_to_project_fields") or {}
        if not rid:
            continue
        out[rid] = {
            "anticipation_frames": int(maps.get("anticipation_frames") or 0),
            "hold_frames": int(maps.get("hold_frames") or 0),
            "duration_frames_hint": int(maps.get("duration_frames_hint") or 0),
        }
    return out
