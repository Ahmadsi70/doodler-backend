"""TDD: storybook_v1 pages from topic — no cutouts, one still per page."""

from __future__ import annotations

from agents.storybook_page_agent import plan_storybook
from libraries.storybook_contract import STORYBOOK_SCHEMA, StorybookPlan


def test_plan_storybook_one_page_per_clause() -> None:
    topic = (
        "A small fox finds a glowing lantern. "
        "Fireflies gather around the light. "
        "The fox walks toward a wooden bridge. "
        "Mist rises from the river. "
        "The fox reaches a quiet hilltop."
    )
    plan = plan_storybook(
        topic, title="Lantern Fox", target_sec=30.0, language="en"
    )
    assert isinstance(plan, StorybookPlan)
    assert plan.schema_version == STORYBOOK_SCHEMA
    assert plan.engine == "storybook"
    assert 4 <= len(plan.pages) <= 6
    assert abs(sum(p.hold_sec for p in plan.pages) - 30.0) < 0.05
    for p in plan.pages:
        assert p.still_prompt
        assert "no text" in p.still_prompt.lower() or "no letters" in p.still_prompt.lower()
        assert "cutout" not in p.still_prompt.lower()
        assert p.camera in {"subtle_zoom_in", "slow_pan_left", "slow_pan_right", "static"}
    assert plan.crossfade_sec > 0


def test_storybook_plan_json_roundtrip() -> None:
    plan = plan_storybook("Sun rises. Rain falls.", title="Weather", target_sec=12.0)
    raw = plan.model_dump_json()
    again = StorybookPlan.model_validate_json(raw)
    assert again.title == "Weather"
    assert len(again.pages) == 2
