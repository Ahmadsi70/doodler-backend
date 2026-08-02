"""TDD: each scene is directed so meaning reads at first glance."""

from __future__ import annotations

from agents.storybook_page_agent import plan_storybook
from libraries.storybook_visual_directing import direct_scene


def test_direct_scene_maps_discovery_to_awe_hook() -> None:
    d = direct_scene(
        "A fox finds a glowing blue lantern in the forest",
        mood="warm",
        page_index=0,
        page_count=5,
    )
    assert d.emotion == "awe"
    assert "hook" in d.visual_hook.lower() or len(d.visual_hook) > 12
    assert d.camera_angle in {"low_angle", "eye_level", "high_angle", "over_shoulder"}
    assert d.shot in {"wide", "medium", "close"}
    assert "lantern" in d.staging.lower() or "glow" in d.staging.lower()


def test_direct_scene_maps_isolation_to_loneliness() -> None:
    d = direct_scene(
        "Mist rises; the fox looks tiny on the path alone",
        mood="tense",
        page_index=2,
        page_count=5,
    )
    assert d.emotion in {"loneliness", "tension", "unease"}
    assert d.shot == "wide" or d.camera_angle == "high_angle"


def test_plan_pages_carry_concept_directing_in_prompt() -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Fireflies gather. Mist rises. Bridge ahead. Hilltop stars.",
        title="Lantern Fox",
        target_sec=30.0,
    )
    emotions = {p.emotion for p in plan.pages}
    assert len(plan.pages) >= 4
    assert len(emotions) >= 2
    for p in plan.pages:
        assert p.concept
        assert p.emotion
        assert p.visual_hook
        assert p.camera_angle
        assert p.staging
        sp = p.still_prompt.lower()
        assert "visual hook" in sp or "first glance" in sp
        assert "concept" in sp
        assert "emotion" in sp
        assert "staging" in sp
