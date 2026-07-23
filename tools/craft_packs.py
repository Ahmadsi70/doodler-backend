"""
Load executable craft data packs (cine / look / transition / audio).

Why: keep Remotion and agents on JSON recipes, not prose books.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / "libraries"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_cine_lexicon() -> dict[str, Any]:
    data = _load(_LIB / "cine" / "lexicon.json")
    if not data.get("shots"):
        raise FileNotFoundError("libraries/cine/lexicon.json missing shots")
    return data


@lru_cache(maxsize=1)
def load_look_bible() -> dict[str, Any]:
    data = _load(_LIB / "look" / "bible.json")
    if not data.get("grades"):
        raise FileNotFoundError("libraries/look/bible.json missing grades")
    return data


@lru_cache(maxsize=1)
def load_transition_grammar() -> dict[str, Any]:
    data = _load(_LIB / "transitions" / "grammar.json")
    if not data.get("transitions"):
        raise FileNotFoundError("libraries/transitions/grammar.json missing transitions")
    return data


@lru_cache(maxsize=1)
def load_audio_cues() -> dict[str, Any]:
    data = _load(_LIB / "audio" / "cues.json")
    if not data.get("cues"):
        raise FileNotFoundError("libraries/audio/cues.json missing cues")
    return data


def resolve_transition(from_beat: str, to_beat: str) -> dict[str, Any]:
    """Pick transition recipe for a beat edge."""
    grammar = load_transition_grammar()
    rules = list(grammar.get("beat_pair_rules") or [])
    fb = (from_beat or "*").lower()
    tb = (to_beat or "*").lower()
    chosen = "crossfade"
    for rule in rules:
        fr = str(rule.get("from_beat") or "*").lower()
        tr = str(rule.get("to_beat") or "*").lower()
        if (fr in {"*", fb}) and (tr in {"*", tb}):
            chosen = str(rule.get("transition") or chosen)
            break
    meta = dict((grammar.get("transitions") or {}).get(chosen) or {})
    meta["id"] = chosen
    meta.setdefault("frames", int(grammar.get("default_frames") or 12))
    return meta


def camera_move_for_beat(beat: str, camera: str) -> dict[str, Any]:
    lex = load_cine_lexicon()
    moves = lex.get("moves") or {}
    defaults = (lex.get("beat_defaults") or {}).get(beat) or {}
    move_id = camera if camera in moves else str(defaults.get("move") or "static")
    if move_id not in moves:
        move_id = "static"
    out = dict(moves.get(move_id) or {"translate_x": 0, "scale_end": 1.0})
    out["id"] = move_id
    return out


def look_for_beat(beat: str, fallback_grade: str = "pastel_muted") -> dict[str, Any]:
    """Per-shot look recipe: grade id + palette + vignette/grain."""
    look = load_look_bible()
    grade_id = str((look.get("beat_grade") or {}).get(beat) or fallback_grade)
    grade = dict((look.get("grades") or {}).get(grade_id) or {})
    if not grade:
        grade_id = fallback_grade
        grade = dict((look.get("grades") or {}).get(grade_id) or {})
    palette = {
        "bg0": str(grade.get("bg0") or "#e8dfe8"),
        "bg1": str(grade.get("bg1") or "#c5d4e8"),
        "bg2": str(grade.get("bg2") or "#9eb8d4"),
        "accent": str(grade.get("accent") or "#7a9eb8"),
        "text": str(grade.get("text") or "#2a3344"),
        "muted": str(grade.get("muted") or "#5a6a7a"),
    }
    return {
        "gradeId": grade_id,
        "palette": palette,
        "vignette": float(grade.get("vignette") or 0.25),
        "grain": float(grade.get("grain") or 0.05),
        "lutStrength": float(grade.get("lut_strength") or 0.1),
        "contrast": float(grade.get("contrast") or 1.0),
        "parallax": float(grade.get("parallax") or 0.4),
        "depthLayers": int(grade.get("depth_layers") or 2),
    }


def shot_size_scale(size: str | None) -> float:
    """Relative framing scale for WS/MS/CU/insert."""
    s = (size or "MS").upper()
    return {"WS": 0.88, "MS": 1.0, "CU": 1.18, "INSERT": 1.28}.get(s, 1.0)
