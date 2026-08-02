"""TDD: story-aware detailed page prompts (craft + optional LLM enrich)."""

from __future__ import annotations

import json

from agents.storybook_page_agent import plan_storybook
from agents.storybook_prompt_director import (
    enrich_plan_prompts,
    parse_director_prompts,
)
from libraries.storybook_prompt_craft import craft_page_still_prompt


def test_crafted_prompts_differ_by_story_beat() -> None:
    plan = plan_storybook(
        "A fox finds a glowing blue lantern. Fireflies gather. "
        "The fox walks toward a wooden bridge. Soft mist rises. Hilltop under stars.",
        title="Lantern Fox",
        target_sec=30.0,
    )
    prompts = [p.still_prompt for p in plan.pages]
    assert len(set(prompts)) == len(prompts)
    blob0 = prompts[0].lower()
    blob_bridge = " ".join(prompts).lower()
    assert "style lock" in blob0
    assert "character bible" in blob0
    assert "negative" in blob0 or "do not" in blob0
    assert "lantern" in blob0 or "blue" in blob0
    assert "bridge" in blob_bridge
    assert "mist" in blob_bridge or "fog" in blob_bridge
    # Scene layer must be longer than the bare action clause
    assert len(prompts[0]) > len(plan.pages[0].visual_action) + 120


def test_parse_director_prompts_keeps_locks() -> None:
    plan = plan_storybook("Sun rises. Rain falls.", title="Weather", target_sec=10.0)
    raw = json.dumps(
        {
            "pages": [
                {
                    "index": 0,
                    "still_prompt": (
                        f"{plan.style_lock} {plan.character_bible} "
                        "PAGE BEAT: sun over hills. NEGATIVE: no text no frame."
                    ),
                },
                {
                    "index": 1,
                    "still_prompt": "rain only without locks",
                },
            ]
        }
    )
    out = parse_director_prompts(raw, plan)
    assert "STYLE LOCK" in out[0] or plan.style_lock[:20] in out[0]
    # Missing locks get grafted
    assert plan.style_lock[:24] in out[1]
    assert plan.character_bible[:24] in out[1]


def test_enrich_plan_prompts_with_inject_fn() -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Mist rises by the bridge.",
        title="Lantern Fox",
        target_sec=12.0,
    )

    def fake_llm(_prompt: str) -> str:
        pages = []
        for p in plan.pages:
            pages.append(
                {
                    "index": p.index,
                    "still_prompt": (
                        f"DIRECTOR DETAIL page {p.index}: {p.visual_action}. "
                        f"Foreground moss, midground hero, background pines. "
                        f"{plan.style_lock} {plan.character_bible} "
                        "NEGATIVE: no text, no picture frame, no oval mat."
                    ),
                }
            )
        return json.dumps({"pages": pages})

    enriched = enrich_plan_prompts(plan, text_fn=fake_llm)
    assert enriched.pages[0].still_prompt != plan.pages[0].still_prompt
    assert "DIRECTOR DETAIL" in enriched.pages[0].still_prompt
    assert plan.style_lock[:20] in enriched.pages[0].still_prompt


def test_craft_includes_shot_and_layers() -> None:
    text = craft_page_still_prompt(
        title="Lantern Fox",
        action="The fox walks toward a wooden bridge.",
        ambiance="dusk",
        topic="fox lantern bridge",
        style_lock="STYLE LOCK: paper-cut",
        character_bible="CHARACTER BIBLE: one fox",
        shot="medium",
        page_index=2,
        page_count=5,
    )
    low = text.lower()
    assert "medium" in low or "midground" in low
    assert "foreground" in low and "background" in low
    assert "bridge" in low
