"""P0: screenplay → script breakdown → storyboard (industry order)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = (
    "Hero enters the quiet room.\n\n"
    "Then they react in shock because the letter burns.\n\n"
    "They leave quietly."
)


def test_draft_screenplay_from_brief_has_scenes():
    from agents.draft_screenplay_agent import run_draft_screenplay_agent

    draft = run_draft_screenplay_agent(BRIEF, runtime_seconds=30, title="Test")
    assert draft["agent"] == "DraftScreenplayAgent"
    assert len(draft["scenes"]) >= 3
    assert "پیش‌نویس نمایشنامه" in draft["screenplay_md"]
    assert draft["scenes"][0]["action"]


def test_script_breakdown_emits_shot_list_with_beats():
    from agents.draft_screenplay_agent import run_draft_screenplay_agent
    from agents.script_breakdown_agent import run_script_breakdown_agent

    draft = run_draft_screenplay_agent(BRIEF, runtime_seconds=30)
    breakdown = run_script_breakdown_agent(draft, brief=BRIEF)
    assert breakdown["agent"] == "ScriptBreakdownAgent"
    assert len(breakdown["shots"]) >= 3
    shot = breakdown["shots"][1]
    assert shot.get("story_beat") == "reaction"
    assert "beat" in breakdown["beats"][0]


def test_storyboard_prefers_breakdown_over_raw_brief():
    from agents.draft_screenplay_agent import run_draft_screenplay_agent
    from agents.script_breakdown_agent import run_script_breakdown_agent
    from agents.story_chain import run_storyboard

    draft = run_draft_screenplay_agent(BRIEF, runtime_seconds=30)
    breakdown = run_script_breakdown_agent(draft, brief=BRIEF)
    board = run_storyboard(BRIEF, runtime_seconds=30, breakdown=breakdown)
    assert board.get("source") == "script_breakdown"
    assert len(board["shots"]) == len(breakdown["shots"])
    assert board["shots"][1].get("story_beat") == "reaction"


def test_chain_manifest_order_screenplay_first(tmp_path: Path):
    from agents.story_chain import AGENT_ORDER, CHAIN_MANIFEST, run_story_agent_chain

    run_story_agent_chain(
        BRIEF,
        tmp_path,
        extras={"runtime_seconds": 30, "use_llm": False, "emotion": "sad"},
    )
    assert AGENT_ORDER[0] == "DraftScreenplayAgent"
    assert AGENT_ORDER[1] == "ScriptBreakdownAgent"
    assert "StoryboardAgent" in AGENT_ORDER
    manifest = json.loads(
        (tmp_path / "agents" / CHAIN_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["order"][0] == "DraftScreenplayAgent"
    agents_dir = tmp_path / "agents"
    assert (agents_dir / "draft_screenplay.json").is_file()
    assert (agents_dir / "script_breakdown.json").is_file()
    assert (agents_dir / "style_recommendation.json").is_file()


def test_chain_carries_draft_screenplay_fields(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain

    chain = run_story_agent_chain(
        BRIEF,
        tmp_path,
        extras={"runtime_seconds": 30, "use_llm": False},
    )
    assert chain.screenplay.get("agent") == "DraftScreenplayAgent"
    assert chain.script_breakdown.get("agent") == "ScriptBreakdownAgent"
    assert chain.style_recommendation.get("primary_style_id")
