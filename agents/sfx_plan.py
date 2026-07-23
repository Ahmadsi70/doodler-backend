"""
SFX plan helpers — infer catalog cue_ids from narrative action (FA/EN).

Why: silent motion stories need typed SFX in breakdown/screenplay that Remotion
can lock to frames; free-form filenames are forbidden.
"""

from __future__ import annotations

import re
from typing import Any

# (kind, preferred_cue_ids, offset_frac, reason_fa, patterns)
_RULES: tuple[tuple[str, tuple[str, ...], float, str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "vocal",
        ("vocal_laugh", "vocal_giggle"),
        0.25,
        "خنده / واکنش صوتی",
        (
            re.compile(r"خند|می‌خند|مي‌خند|قهقه|giggl|laugh|chuckl", re.I),
        ),
    ),
    (
        "whoosh",
        ("whoosh_move",),
        0.15,
        "حرکت سریع / عبور",
        (
            re.compile(
                r"می‌دود|ميدود|می‌پرد|پرش|شتاب|whoosh|dash|rush|fly|پرواز",
                re.I,
            ),
        ),
    ),
    (
        "footstep",
        ("foley_footstep",),
        0.2,
        "قدم / ورود",
        (
            re.compile(
                r"وارد|قدم|راه می‌رود|راه ميرود|قدم می‌زند|گام|walk|enter|step|foot",
                re.I,
            ),
        ),
    ),
    (
        "prop",
        ("prop_pickup", "foley_hit_soft"),
        0.45,
        "برداشتن / لمس شیء",
        (
            re.compile(
                r"برمی‌دارد|برمیدارد|برمي‌دارد|جعبه|قلم|نامه|کلید|در |بسته|pickup|grab|pick up|open",
                re.I,
            ),
        ),
    ),
    (
        "cloth",
        ("cloth_rustle",),
        0.35,
        "حرکت لباس / پارچه",
        (
            re.compile(r"لباس|پارچه|شنل|ردا|cloak|cloth|rustle|sleeve", re.I),
        ),
    ),
    (
        "magic",
        ("magic_sparkle", "stinger_reveal"),
        0.5,
        "جادو / درخشش",
        (
            re.compile(r"روشن می‌شود|درخش|جادو|فانوس|glow|spark|magic|reveal", re.I),
        ),
    ),
)

_BEAT_DEFAULTS: dict[str, tuple[str, tuple[str, ...], float, str]] = {
    "entrance": ("footstep", ("foley_footstep", "whoosh_move"), 0.2, "ورود"),
    "exit": ("footstep", ("foley_footstep",), 0.7, "خروج"),
    "reveal": ("prop", ("prop_pickup", "stinger_reveal"), 0.45, "افشا"),
    "reaction": ("vocal", ("vocal_laugh", "foley_hit_soft"), 0.3, "واکنش"),
    "conflict": ("impact", ("foley_hit_soft",), 0.4, "درگیری"),
}


def _first_existing(cues: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    for cid in candidates:
        if cid in cues and not (cues[cid] or {}).get("alias_of"):
            return cid
        if cid in cues:
            return cid
    # soft match: footstep alias or any tagged
    for cid, row in cues.items():
        if row.get("role") == "bed":
            continue
        tags = {str(t).lower() for t in (row.get("tags") or [])}
        for cand in candidates:
            key = cand.replace("foley_", "").split("_")[0]
            if key in cid or key in tags:
                if not row.get("alias_of"):
                    return cid
    for cid in candidates:
        if cid in cues:
            return cid
    return None


def infer_sfx_events(
    action: str,
    *,
    beat: str = "",
    catalog_cues: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Infer ordered SFX events for one shot.

    Each event: cue_id, offset_frac, kind, reason_fa — cue_id must exist in catalog
    when catalog_cues is provided.
    """
    cues = catalog_cues if catalog_cues is not None else {}
    text = action or ""
    found: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()

    for kind, prefer, frac, reason, patterns in _RULES:
        if kind in seen_kinds:
            continue
        if not any(p.search(text) for p in patterns):
            continue
        cue_id = _first_existing(cues, prefer) if cues else prefer[0]
        if not cue_id:
            continue
        found.append(
            {
                "cue_id": cue_id,
                "offset_frac": frac,
                "kind": kind,
                "reason_fa": reason,
            }
        )
        seen_kinds.add(kind)

    beat_l = (beat or "").lower()
    if not found and beat_l in _BEAT_DEFAULTS:
        kind, prefer, frac, reason = _BEAT_DEFAULTS[beat_l]
        cue_id = _first_existing(cues, prefer) if cues else prefer[0]
        if cue_id:
            found.append(
                {
                    "cue_id": cue_id,
                    "offset_frac": frac,
                    "kind": kind,
                    "reason_fa": reason,
                }
            )
    elif beat_l == "entrance" and "footstep" not in seen_kinds:
        cue_id = (
            _first_existing(cues, ("foley_footstep", "whoosh_move"))
            if cues
            else "foley_footstep"
        )
        if cue_id:
            found.insert(
                0,
                {
                    "cue_id": cue_id,
                    "offset_frac": 0.2,
                    "kind": "footstep",
                    "reason_fa": "ورود",
                },
            )

    return found


def format_sfx_md(events: list[dict[str, Any]]) -> str:
    """Markdown block for screenplay SFX section."""
    if not events:
        return ""
    lines = ["**افکت صدا (SFX):**"]
    for e in events:
        frac = float(e.get("offset_frac") or 0)
        pct = int(round(frac * 100))
        lines.append(
            f"- `{e.get('cue_id')}` @ {pct}% — {e.get('reason_fa') or e.get('kind') or ''}"
        )
    return "\n".join(lines)
