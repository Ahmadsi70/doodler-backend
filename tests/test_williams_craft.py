"""Williams craft pack: load, validate, apply to timing/cinematography."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_williams_pack_lists_four_core_files():
    from libraries import list_libraries

    names = list_libraries("williams")
    for required in (
        "principles.json",
        "timing_recipes.json",
        "shot_behaviors.json",
        "anti_patterns.json",
        "meta.json",
    ):
        assert required in names, required


def test_williams_pack_loads_and_validates():
    from tools.williams_craft import load_williams_craft_pack

    pack = load_williams_craft_pack()
    assert pack.fps == 24
    assert len(pack.principles) >= 10
    assert len(pack.timing_recipes) >= 5
    assert len(pack.shot_behaviors) >= 3
    assert len(pack.anti_patterns) >= 3
    ids = {p["id"] for p in pack.principles}
    assert "set_the_tempo_timing" in ids
    # story pack anti_patterns must remain a separate schema
    from libraries import load_library

    story_ap = load_library("story", "anti_patterns.json")
    assert isinstance(story_ap, list)
    assert story_ap[0].get("pattern_id") == "AP_001"


def test_timing_recipes_json_parses_and_has_no_null_or_range_holes():
    from tools.williams_craft import load_williams_craft_pack

    pack = load_williams_craft_pack()
    for recipe in pack.timing_recipes:
        assert recipe.get("id")
        for phase in recipe.get("phases") or []:
            assert "or_range" in phase
            assert phase["or_range"] is None or isinstance(phase["or_range"], list)
        maps = recipe.get("maps_to_project_fields") or {}
        # low-confidence rows must be backfilled from timing_rules
        if float(recipe.get("confidence") or 0) < 0.6:
            assert int(maps.get("anticipation_frames") or 0) >= 0
            assert (
                int(maps.get("hold_frames") or 0) > 0
                or int(maps.get("duration_frames_hint") or 0) > 0
                or int(maps.get("anticipation_frames") or 0) > 0
            ), recipe["id"]


def test_apply_shot_behavior_enriches_timing_and_cine():
    from tools.williams_craft import apply_williams_craft

    storyboard = {
        "shots": [
            {
                "shot_id": 0,
                "title": "Open",
                "action": "Hero enters the room.",
                "duration_sec": 3.0,
            },
            {
                "shot_id": 1,
                "title": "Hit",
                "action": "Then they react in shock because the letter burns.",
                "duration_sec": 3.5,
            },
            {
                "shot_id": 2,
                "title": "Close",
                "action": "They leave quietly.",
                "duration_sec": 2.5,
            },
        ]
    }
    timing = {
        "fps": 24,
        "shots": [
            {
                "shot_id": 0,
                "duration_sec": 3.0,
                "duration_frames": 72,
                "hold_frames": 12,
                "anticipation_frames": 6,
            },
            {
                "shot_id": 1,
                "duration_sec": 3.5,
                "duration_frames": 84,
                "hold_frames": 12,
                "anticipation_frames": 6,
            },
            {
                "shot_id": 2,
                "duration_sec": 2.5,
                "duration_frames": 60,
                "hold_frames": 12,
                "anticipation_frames": 6,
            },
        ],
    }
    cine = {
        "frames": [
            {"shot_id": 0, "lens": "standard", "camera": "static", "composition": "C"},
            {"shot_id": 1, "lens": "standard", "camera": "static", "composition": "L"},
            {"shot_id": 2, "lens": "beauty", "camera": "static", "composition": "C"},
        ]
    }
    out_timing, out_cine, notes = apply_williams_craft(
        storyboard, timing, cine
    )
    assert any("williams_craft" in n for n in notes)
    shock = next(s for s in out_timing["shots"] if s["shot_id"] == 1)
    assert int(shock["anticipation_frames"]) >= 4
    assert int(shock["hold_frames"]) >= 12
    shock_fr = next(f for f in out_cine["frames"] if f["shot_id"] == 1)
    assert shock_fr["camera"] == "motivated_push"
    assert shock_fr["lens"] == "action"
    assert shock.get("williams_behavior_id")


def test_run_animation_timing_uses_williams_craft():
    from agents.story_chain import run_animation_timing, run_cinematography, run_storyboard

    board = run_storyboard(
        "Hero enters.\n\nThen reacts in shock because fire.\n\nLeaves.",
        runtime_seconds=30,
    )
    cine = run_cinematography(board)
    timing = run_animation_timing(board, fps=24, cinematography=cine)
    assert timing.get("williams_craft_applied") is True
    assert any(s.get("williams_behavior_id") for s in timing.get("shots") or [])
