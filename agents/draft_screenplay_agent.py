"""
DraftScreenplayAgent — first-pass screenplay from brief before storyboard.

Why: industry order puts readable script before visual breakdown; storyboard
must derive from screenplay beats, not raw brief paragraphs alone.
"""

from __future__ import annotations

import hashlib
from typing import Any

try:
    from tools.chapter_tools import split_chapters
except ImportError:
    from ..tools.chapter_tools import split_chapters  # type: ignore


_screenplay_cache: dict[str, dict[str, Any]] = {}


def _cache_key(brief: str, runtime_seconds: float | None = None) -> str:
    """Generate cache key from brief and runtime."""
    content = f"{brief}:{runtime_seconds}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def run_draft_screenplay_agent(
    brief: str,
    *,
    runtime_seconds: float | None = None,
    title: str = "Story",
) -> dict[str, Any]:
    """Build draft screenplay scenes and markdown from a narrative brief."""
    # OPTIMIZATION: Check cache first
    cache_key = _cache_key(brief, runtime_seconds)
    if cache_key in _screenplay_cache:
        return _screenplay_cache[cache_key]
    
    chapters = split_chapters(
        brief, total_seconds=runtime_seconds, studio="story"
    )
    budget = runtime_seconds
    if budget is None and chapters:
        budget = sum(float(c.seconds) for c in chapters)
    scenes: list[dict[str, Any]] = []
    md_lines = [
        f"# پیش‌نویس نمایشنامه — {title}",
        "",
        f"**مدت تقریبی:** ~{float(budget or 0):.0f}s",
        "",
        "---",
        "",
    ]
    for ch in chapters:
        scenes.append(
            {
                "index": ch.index,
                "title": ch.title,
                "action": ch.body,
                "duration_sec": round(float(ch.seconds), 3),
            }
        )
        md_lines.extend(
            [
                f"## صحنه {ch.index + 1} — {ch.title}",
                "",
                ch.body,
                "",
                "---",
                "",
            ]
        )
    result = {
        "agent": "DraftScreenplayAgent",
        "version": "1",
        "title": title,
        "scene_count": len(scenes),
        "scenes": scenes,
        "screenplay_md": "\n".join(md_lines),
        "schema": "draft_screenplay_agent.md#v1",
    }
    # OPTIMIZATION: Cache the result
    _screenplay_cache[cache_key] = result
    return result
