"""TDD: 7-scene Arvin invention story pack with locked continuity."""

from __future__ import annotations

from libraries.storybook_scene_pack import (
    ARVIN_LAST_INVENTION,
    plan_from_scene_pack,
)


def test_arvin_pack_has_seven_directed_scenes() -> None:
    plan = plan_from_scene_pack(ARVIN_LAST_INVENTION, target_sec=49.0)
    assert plan.title.startswith("آخرین") or "Invention" in plan.title or "اختراع" in plan.title
    assert len(plan.pages) == 7
    assert "arvin" in plan.character_bible.lower() or "آروین" in plan.character_bible
    assert "watercolor" in plan.style_lock.lower() or "آبرنگ" in plan.style_lock
    assert "wooden" in plan.character_bible.lower() or "جعبه" in plan.character_bible
    emotions = [p.emotion for p in plan.pages]
    assert emotions[0] in {"awe", "curiosity", "mystery"}
    assert emotions[-1] in {"warmth", "hope", "joy", "belonging"}
    for p in plan.pages:
        assert "arvin" in p.still_prompt.lower() or "آروین" in p.still_prompt
        assert "visual hook" in p.still_prompt.lower() or "first glance" in p.still_prompt.lower()
        assert "concept" in p.still_prompt.lower()
        assert p.hold_sec > 0
