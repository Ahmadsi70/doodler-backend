"""Code-first StudioSpec: full control without free-text agent guessing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_studio_spec_roundtrip_and_compile():
    from studio_spec import ShotControl, StudioSpec
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="Code Studio",
        quality="light",
        mode="direct",
        runtime_seconds=18,
        character_path=None,
        shots=[
            ShotControl(
                action="Hero enters the archive.",
                duration_sec=3.0,
                lens="standard",
                camera="static",
                composition="L",
                pose="walk",
                expression="neutral",
                story_beat="entrance",
                anticipation_frames=6,
                hold_frames=12,
            ),
            ShotControl(
                action="Then shock hits because the letter burns.",
                duration_sec=4.0,
                lens="action",
                camera="motivated_push",
                composition="C",
                pose="react",
                expression="shock",
                story_beat="reaction",
                anticipation_frames=8,
                hold_frames=16,
            ),
            ShotControl(
                action="They leave into rain.",
                duration_sec=3.0,
                lens="beauty",
                camera="static",
                composition="R",
                pose="walk",
                expression="worry",
                story_beat="exit",
            ),
        ],
    )
    raw = spec.model_dump()
    again = StudioSpec.model_validate(raw)
    assert again.mode == "direct"
    assert len(again.shots) == 3

    compiled = compile_studio_spec(spec)
    assert len(compiled.storyboard["shots"]) == 3
    assert compiled.storyboard["shots"][1]["verb"]
    assert compiled.cinematography["frames"][1]["camera"] == "motivated_push"
    assert compiled.timing["shots"][1]["anticipation_frames"] == 8
    assert compiled.timing["shots"][1]["hold_frames"] == 16
    assert compiled.timing["shots"][0]["williams_behavior_id"] or compiled.timing[
        "shots"
    ][0].get("williams_story_beat")
    assert compiled.control_plane == "studio_spec"


def test_studio_spec_json_file_load(tmp_path: Path):
    from studio_spec import StudioSpec
    from tools.studio_api import load_studio_spec, write_studio_spec_example

    example = write_studio_spec_example(tmp_path / "example_studio_spec.json")
    assert example.is_file()
    loaded = load_studio_spec(example)
    assert isinstance(loaded, StudioSpec)
    assert loaded.shots


def test_render_from_spec_light(tmp_path, monkeypatch):
    from studio_spec import ShotControl, StudioSpec
    from tools import studio_api

    # Point job workspace into tmp
    monkeypatch.setenv("ANIMATION_OUT_ROOT", str(tmp_path))
    monkeypatch.setenv("ANIMATION_DETERMINISTIC_SLIDES", "1")

    spec = StudioSpec(
        title="Direct Light",
        quality="light",
        mode="direct",
        runtime_seconds=12,
        use_agents=False,
        shots=[
            ShotControl(action="Enter.", duration_sec=2.0, story_beat="entrance", pose="walk"),
            ShotControl(
                action="Then react because fire.",
                duration_sec=2.5,
                story_beat="reaction",
                pose="react",
                expression="shock",
                camera="motivated_push",
                lens="action",
            ),
            ShotControl(action="Exit.", duration_sec=2.0, story_beat="exit", pose="walk"),
        ],
    )
    result = studio_api.render_from_spec(spec, job_id="spec_light_1")
    assert result.get("ok") is True
    assert result.get("exported") is True
    assert result.get("control_plane") == "studio_spec"
    assert (Path(result["job_dir"]) / "agents" / "storyboard.json").is_file()
    assert (Path(result["job_dir"]) / "studio_spec.json").is_file()
    export_root = Path(str((result.get("artifacts") or {}).get("export_root") or ""))
    assert export_root.is_dir()
    assert (export_root / "screenplay.md").is_file()
