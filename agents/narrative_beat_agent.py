"""
NarrativeBeatAgent — topic/prose → silent visual beats (no dialogue).

Why: dialogueless cinematic stories need readable beat timing before cast/cutouts.
Works for any topic; mock path is deterministic (no LLM required).
"""

from __future__ import annotations

import re
from typing import Any

from libraries.silent_beats import CameraHint, NarrativeBeat

_SPLIT_RE = re.compile(
    r"(?<=[.!?؟۔…])\s+|(?<=[;؛])\s+|\n+|(?<=،)\s+(?=[آ-یA-Za-z])",
    re.UNICODE,
)
_CAMERA_WORDS: list[tuple[re.Pattern[str], CameraHint]] = [
    (re.compile(r"\b(left|چپ)\b", re.I), "slow_pan_left"),
    (re.compile(r"\b(right|راست)\b", re.I), "slow_pan_right"),
    (re.compile(r"\b(still|static|ثابت)\b", re.I), "static"),
]


_META_CLAUSE_RE = re.compile(
    r"^\s*(no\s+text|no\s+dialogue|no\s+speech|بدون\s*متن|بدون\s*دیالوگ|"
    r"silent\s+only|without\s+text|without\s+dialogue)\b",
    re.I,
)


def _is_meta_clause(clause: str) -> bool:
    """True for production instructions that must not become visual beats."""
    c = (clause or "").strip()
    if not c:
        return True
    if _META_CLAUSE_RE.search(c):
        return True
    low = c.lower()
    # Whole-clause meta (avoid dropping real story lines that mention rain text etc.)
    if low in {"no text.", "no dialogue.", "no text, no dialogue."}:
        return True
    if re.fullmatch(r"no[\w\s,]+dialogue\.?", low):
        return True
    return False


def _split_clauses(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip(" -\t") for p in _SPLIT_RE.split(raw) if p and p.strip()]
    if len(parts) <= 1:
        # Fallback: comma / dash chunks for short prompts
        parts = [
            p.strip()
            for p in re.split(r"\s*[,–—\-]\s+", raw)
            if p.strip() and len(p.strip()) > 2
        ]
    parts = [p for p in parts if not _is_meta_clause(p)]
    return parts or [raw]


def _camera_hint(action: str) -> CameraHint:
    for pat, hint in _CAMERA_WORDS:
        if pat.search(action):
            return hint
    return "subtle_zoom_in"


def _mood(action: str) -> str:
    low = action.lower()
    if any(w in low for w in ("storm", "باران", "night", "شب", "fear")):
        return "tense"
    if any(w in low for w in ("sun", "آفتاب", "glow", "warm", "گرم")):
        return "warm"
    if any(w in low for w in ("grow", "رشد", "sprout", "جوانه")):
        return "hopeful"
    return "calm"


def plan_silent_beats(
    topic: str,
    *,
    target_sec: float = 60.0,
    language: str = "fa",
    max_beats: int = 12,
) -> list[NarrativeBeat]:
    """
    Deterministic silent beat plan from topic/prose.

    Why: CI and offline pods need narrative pacing without Gemini; live enrich
    can replace clauses later while keeping the same contract.
    """
    _ = language  # reserved for live LLM locale prompts
    clauses = _split_clauses(topic)[: max(1, int(max_beats))]
    if not clauses:
        clauses = ["A quiet scene unfolds"]
    dur = max(4.0, float(target_sec))
    # Leave a short open + close buffer for camera settle
    usable = max(3.0, dur * 0.92)
    hold = usable / float(len(clauses))
    beats: list[NarrativeBeat] = []
    for i, clause in enumerate(clauses):
        beats.append(
            NarrativeBeat(
                index=i,
                visual_action=clause,
                hold_sec=round(hold, 3),
                camera_hint=_camera_hint(clause),
                mood=_mood(clause),
                dialogue="",
            )
        )
    # Fix float drift so sum ≈ target
    drift = dur - sum(b.hold_sec for b in beats)
    if beats and abs(drift) > 1e-6:
        last = beats[-1]
        beats[-1] = last.model_copy(
            update={"hold_sec": round(max(0.5, last.hold_sec + drift), 3)}
        )
    return beats


def run_narrative_beat_agent(
    topic: str,
    *,
    target_sec: float = 60.0,
    language: str = "fa",
    title: str = "Story",
) -> dict[str, Any]:
    """AgentBus entry — silent beats JSON."""
    beats = plan_silent_beats(topic, target_sec=target_sec, language=language)
    return {
        "agent": "NarrativeBeatAgent",
        "version": "1",
        "title": title,
        "topic": topic,
        "language": language,
        "target_sec": float(target_sec),
        "no_dialogue": True,
        "beats": [b.model_dump(mode="json") for b in beats],
    }
