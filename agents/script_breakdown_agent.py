"""
ScriptBreakdownAgent — beats, dialogue, SFX, and shot list from draft screenplay.

Why: storyboard/cine need a structured shot list; silent narratives also need
typed SFX cue_ids grounded in action so Remotion stays frame-synced.
"""

from __future__ import annotations

import re
from typing import Any

try:
    from tools.williams_craft import infer_story_beat
except ImportError:
    from ..tools.williams_craft import infer_story_beat  # type: ignore

_DIALOGUE_RE = re.compile(
    r"[«\"]([^»\"]{1,240})[»\"]|(?:^|\n)\s*(?:DIALOGUE|دیالوگ)\s*[:：]\s*(.+)",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_dialogue(action: str) -> str:
    """Pull quoted or labeled dialogue from scene action text."""
    text = (action or "").strip()
    if not text:
        return ""
    match = _DIALOGUE_RE.search(text)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def run_script_breakdown_agent(
    draft: dict[str, Any],
    *,
    brief: str = "",
) -> dict[str, Any]:
    """Convert draft screenplay scenes into a shot list with beats, dialogue, SFX."""
    from agents.sfx_plan import infer_sfx_events

    try:
        from agents.audio_cue_agent import load_audio_catalog
        from tools.audio_cues import ensure_audio_cue_files

        ensure_audio_cue_files()
        catalog_cues = dict(load_audio_catalog().get("cues") or {})
    except Exception:  # noqa: BLE001
        catalog_cues = {}

    scenes = list(draft.get("scenes") or [])
    if not scenes and brief.strip():
        from agents.draft_screenplay_agent import run_draft_screenplay_agent

        draft = run_draft_screenplay_agent(brief)
        scenes = list(draft.get("scenes") or [])
    total = max(1, len(scenes))
    shots: list[dict[str, Any]] = []
    beats: list[dict[str, Any]] = []
    for i, sc in enumerate(scenes):
        action = str(sc.get("action") or "")
        beat = str(
            sc.get("story_beat")
            or infer_story_beat(action, index=i, total=total)
        )
        dialogue = str(sc.get("dialogue") or _extract_dialogue(action))
        sid = sc.get("index", i)
        sfx = list(sc.get("sfx") or [])
        if not sfx:
            sfx = infer_sfx_events(action, beat=beat, catalog_cues=catalog_cues)
        shots.append(
            {
                "shot_id": sid,
                "title": str(sc.get("title") or f"Shot {i + 1}"),
                "action": action,
                "dialogue": dialogue,
                "duration_sec": round(float(sc.get("duration_sec") or 3.0), 3),
                "story_beat": beat,
                "sfx": sfx,
            }
        )
        beats.append(
            {
                "index": i,
                "beat": beat,
                "dialogue": dialogue or None,
                "sfx_count": len(sfx),
            }
        )
    return {
        "agent": "ScriptBreakdownAgent",
        "version": "2",
        "shot_count": len(shots),
        "shots": shots,
        "beats": beats,
        "source": "draft_screenplay",
        "schema": "script_breakdown_agent.md#v2",
    }
