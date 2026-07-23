"""Tests for export-pack agents (screenplay, notes, prompts, gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _spec() -> StudioSpec:
    return StudioSpec(
        title="آزمون",
        runtime_seconds=10,
        shots=[
            ShotControl(
                title="ورود",
                action="قهرمان وارد سالن می‌شود.",
                duration_sec=3,
                pose="walk",
                story_beat="entrance",
                camera="static",
                dialogue="سلام.",
            ),
            ShotControl(
                title="شوک",
                action="با شوک واکنش نشان می‌دهد.",
                duration_sec=4,
                pose="react",
                expression="shock",
                story_beat="reaction",
                camera="motivated_push",
            ),
        ],
    )


def test_screenplay_agent_json_and_md():
    from agents.screenplay_agent import run_screenplay_agent

    out = run_screenplay_agent(_spec())
    assert out["version"] == "1"
    assert len(out["shots"]) == 2
    assert "نمایشنامه" in out["screenplay_md"]
    assert out["shots"][0]["beat_fa"]


def test_director_notes_agent():
    from agents.director_notes_agent import run_director_notes_agent

    out = run_director_notes_agent(_spec())
    assert "توضیح ساخت" in out["explanation_md"]
    assert len(out["shot_notes"]) == 2
    assert out["shot_notes"][1]["camera_fa"]


def test_prompt_craft_agent_negative_and_film():
    from agents.prompt_craft_agent import run_prompt_craft_agent

    out = run_prompt_craft_agent(_spec())
    assert out["film_prompt"]
    assert len(out["shots"]) == 2
    assert out["shots"][0]["prompt"]
    assert "negative" in out["shots"][0]
    assert "motion" in out["guide_md"] or "Story" in out["guide_md"]


def test_export_bundle_gate_passes_complete_bundle(tmp_path):
    from tools.export_bundle_gate import run_export_bundle_gate
    from tools.animation_export import export_animation_bundle

    bundle = export_animation_bundle(_spec(), tmp_path / "b", targets=["prompts"])
    assert bundle["ok"] is True
    gate = run_export_bundle_gate(Path(bundle["export_root"]), targets=["prompts"])
    assert gate["ok"] is True
    assert gate["missing"] == []


def test_export_bundle_uses_agents(tmp_path):
    from tools.animation_export import export_animation_bundle

    root = Path(export_animation_bundle(_spec(), tmp_path / "b")["export_root"])
    sp_json = json.loads((root / "screenplay.json").read_text(encoding="utf-8"))
    assert sp_json["title"] == "آزمون"
    assert (root / "prompts" / "shot_00_negative.txt").is_file()
    gate = json.loads((root / "export_gate.json").read_text(encoding="utf-8"))
    assert gate["ok"] is True
