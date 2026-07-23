"""
StyleRecommenderAgent — suggest visual style from brief keywords + emotion.

Why: no dedicated style agent exists; authors need data-driven picks from starter_pack.
"""

from __future__ import annotations

import re
from typing import Any

_STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ink_bw_editorial": (
        "سیاه",
        "سفید",
        "نامه",
        "عکس",
        "خاطره",
        "bw",
        "editorial",
        "خط",
    ),
    "moody_portrait_brand": (
        "غم",
        "چهره",
        "نزدیک",
        "احساس",
        "اشک",
        "sad",
        "portrait",
        "rim",
    ),
    "surreal_dream_cut": (
        "مه",
        "رویا",
        "مرموز",
        "نماد",
        "dream",
        "mist",
        "fog",
        "symbol",
    ),
    "epic_wide_myth": (
        "وسیع",
        "افق",
        "حماسه",
        "منظره",
        "wide",
        "epic",
        "landscape",
    ),
    "neon_noir_chase": (
        "شب",
        "شهر",
        "تعقیب",
        "نئون",
        "noir",
        "chase",
        "urban",
    ),
    "symmetrical_pastel_cinema": (
        "pastel",
        "ملایم",
        "متقارن",
        "لطیف",
        "whimsical",
        "symmetry",
    ),
    "storybook_character_line": (
        "کودک",
        "داستان",
        "کتاب",
        "storybook",
        "cute",
    ),
    "comic_panel_beats": (
        "کمیک",
        "پنل",
        "comic",
        "bold",
    ),
    "documentary_truth_light": (
        "مستند",
        "واقع",
        "documentary",
        "truth",
    ),
}

_EMOTION_BOOST: dict[str, tuple[str, ...]] = {
    "sad": ("ink_bw_editorial", "moody_portrait_brand", "surreal_dream_cut"),
    "happy": ("symmetrical_pastel_cinema", "storybook_character_line"),
    "angry": ("neon_noir_chase", "comic_panel_beats"),
    "surprised": ("surreal_dream_cut", "comic_panel_beats"),
    "neutral": ("symmetrical_pastel_cinema", "documentary_truth_light"),
}


def _score_style(style_id: str, text: str, emotion: str) -> float:
    score = 0.0
    low = text.lower()
    for kw in _STYLE_KEYWORDS.get(style_id, ()):
        if kw.lower() in low:
            score += 2.0
    if style_id in _EMOTION_BOOST.get(emotion.lower(), ()):
        score += 1.5
    return score


def recommend_styles(
    brief: str,
    *,
    emotion: str = "neutral",
    current_style_id: str | None = None,
    top_n: int = 3,
) -> dict[str, Any]:
    """Rank starter_pack styles; return primary + alternatives with Persian rationale."""
    from tools.style_catalog import get_style, list_styles

    text = re.sub(r"\s+", " ", (brief or "").strip())
    ranked: list[tuple[str, float]] = []
    for row in list_styles():
        sid = str(row.get("style_id") or "")
        if not sid:
            continue
        ranked.append((sid, _score_style(sid, text, emotion)))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    if not ranked or ranked[0][1] <= 0:
        primary = current_style_id or "symmetrical_pastel_cinema"
        alts = [s for s, _ in ranked[:top_n] if s != primary][: top_n - 1]
    else:
        primary = ranked[0][0]
        alts = [s for s, sc in ranked[1:] if sc > 0 and s != primary][: top_n - 1]

    primary_meta = get_style(primary) or {}
    traits = ", ".join((primary_meta.get("prompt_traits") or [])[:3])
    rationale = (
        f"بر اساس کلیدواژه‌های brief و emotion={emotion}، "
        f"«{primary_meta.get('name') or primary}» ({primary}) پیشنهاد می‌شود"
        + (f" — traits: {traits}" if traits else "")
        + "."
    )
    if current_style_id and current_style_id != primary:
        rationale += f" سبک فعلی شما `{current_style_id}` است؛ در صورت تمایل مقایسه کنید."

    return {
        "version": "1",
        "primary_style_id": primary,
        "alternatives": alts,
        "scores": {sid: sc for sid, sc in ranked if sc > 0},
        "emotion": emotion,
        "rationale_fa": rationale,
    }
