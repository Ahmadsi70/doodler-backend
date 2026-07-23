"""Director UI data: craft load, prompt overrides, export readiness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = "Hero enters.\n\nThen reacts.\n\nLeaves."


def test_prompt_override_commands(tmp_path: Path):
    from tools.director_ui_data import apply_prompt_override_commands, load_prompt_overrides

    data, notes = apply_prompt_override_commands(
        tmp_path,
        "prompt shot_00: misty platform\nnegative shot_00: blur\nfilm: wide mood",
    )
    assert "shot_00" in data["shot_prompts"]
    assert data["shot_prompts"]["shot_00"] == "misty platform"
    assert data["film_prompt"] == "wide mood"
    loaded = load_prompt_overrides(tmp_path)
    assert loaded["shot_negatives"]["shot_00"] == "blur"
    assert any("prompt" in n for n in notes)


def test_merge_export_preview(tmp_path: Path):
    from tools.director_ui_data import merge_export_preview, save_prompt_overrides

    base = {
        "film_prompt": "a",
        "shot_prompts": {"shot_00": "x"},
        "shot_negatives": {},
        "shot_motions": {},
    }
    save_prompt_overrides(
        tmp_path,
        {"shot_prompts": {"shot_00": "override"}, "film_prompt": "film2"},
    )
    from tools.director_ui_data import load_prompt_overrides

    merged = merge_export_preview(base, load_prompt_overrides(tmp_path))
    assert merged["shot_prompts"]["shot_00"] == "override"
    assert merged["film_prompt"] == "film2"


def test_load_craft_bundle_after_design(tmp_path: Path):
    from tools.director_board import design_from_brief
    from tools.director_ui_data import breakdown_table_rows, load_craft_bundle

    design_from_brief(BRIEF, job_dir=tmp_path, runtime_seconds=20, use_llm=False)
    bundle = load_craft_bundle(tmp_path)
    assert bundle["available"]
    assert breakdown_table_rows(bundle)


def test_revise_dialogue_and_beat():
    from tools.director_board import apply_revise_prompt
    from studio_spec import ShotControl, StudioSpec

    spec = StudioSpec(
        title="t",
        shots=[
            ShotControl(title="a", action="walks", story_beat="entrance"),
            ShotControl(title="b", action="stops", story_beat="decision"),
        ],
    )
    spec2, notes = apply_revise_prompt(
        spec,
        "shot 1\ndialogue: سلام\nbeat: reaction",
        shot_indices=[1],
    )
    assert spec2.shots[1].dialogue == "سلام"
    assert spec2.shots[1].story_beat == "reaction"
    assert notes
