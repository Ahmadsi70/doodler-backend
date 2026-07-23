"""
DraftScreenplayAgent — first-pass screenplay from brief before storyboard.

Why: industry order puts readable script before visual breakdown; storyboard
must derive from screenplay beats, not raw brief paragraphs alone.
"""

from __future__ import annotations

from typing import Any

try:
    from tools.chapter_tools import split_chapters
except ImportError:
    from ..tools.chapter_tools import split_chapters  # type: ignore


def run_draft_screenplay_agent(
    brief: str,
    *,
    runtime_seconds: float | None = None,
    title: str = "Story",
) -> dict[str, Any]:
    """Build draft screenplay scenes and markdown from a narrative brief."""
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
    return {
        "agent": "DraftScreenplayAgent",
        "version": "1",
        "title": title,
        "scene_count": len(scenes),
        "scenes": scenes,
        "screenplay_md": "\n".join(md_lines),
        "schema": "draft_screenplay_agent.md#v1",
    }
