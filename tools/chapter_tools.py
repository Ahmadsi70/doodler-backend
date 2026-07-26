"""Split briefs into timed narrative shots for Story."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    body: str
    seconds: float


def split_chapters(
    brief: str,
    *,
    total_seconds: float | None = None,
    max_chapters: int = 48,
    studio: str = "story",
) -> list[Chapter]:
    text = (brief or "").strip()
    if not text:
        return [Chapter(0, "Untitled", "…", 3.0)]

    cleaned_lines = []
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("runtime_seconds=") or low.startswith("story narrative"):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip() or brief.strip()

    parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(parts) < 2:
        parts = [s.strip() for s in re.split(r"(?<=[.!?\u060c])\s*", text) if s.strip()]
    if not parts:
        parts = [text]
    parts = parts[:max_chapters]

    budget = float(total_seconds) if total_seconds and total_seconds > 0 else None
    if budget is None:
        per = 3.5
        seconds_list = [per] * len(parts)
    else:
        base = max(2.0, budget / max(1, len(parts)))
        seconds_list = [base] * len(parts)
        drift = budget - sum(seconds_list)
        seconds_list[-1] = max(2.0, seconds_list[-1] + drift)

    chapters: list[Chapter] = []
    for i, body in enumerate(parts):
        chapters.append(
            Chapter(
                index=i,
                title=f"Shot {i + 1}",
                body=body,
                seconds=float(seconds_list[i]),
            )
        )
    return chapters


_DURATION_RE = re.compile(r"(\d+)\s*(?:ثانیه|second|sec)", re.IGNORECASE)


def extract_runtime_seconds(text: str) -> float | None:
    """Parse a Persian/English duration hint like \"۵ ثانیه‌ای\" → 5.0."""
    if not text:
        return None
    m = _DURATION_RE.search(text)
    if m:
        # Convert Persian digits if needed
        digits = m.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        try:
            return float(digits)
        except ValueError:
            return None
    return None


def chapters_to_jsonable(chapters: Sequence[Chapter]) -> list[dict]:
    return [
        {
            "index": c.index,
            "title": c.title,
            "body": c.body,
            "seconds": c.seconds,
        }
        for c in chapters
    ]
