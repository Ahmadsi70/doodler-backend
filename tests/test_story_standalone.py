"""Story standalone core contracts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_no_animation_engine_on_sys_path():
    bad = [p for p in sys.path if "AnimationEngine" in p.replace("\\", "/")]
    assert not bad


def test_pack_is_story():
    from libraries import list_libraries
    from tools.studio_router import pack_for_studio

    assert pack_for_studio() == "story"
    names = list_libraries("story")
    assert "scene_schema.json" in names
    assert "timing_rules.json" in names


def test_profiles_story_only():
    from tools.render_profiles import RENDER_PROFILES, get_render_profile

    assert {k[0] for k in RENDER_PROFILES} == {"studio_story"}
    assert get_render_profile("x", "pro").backend == "remotion"


def test_story_chain(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain

    r = run_story_agent_chain(
        "Hero enters.\n\nThen finds the letter because light hits it.\n\nSteps forward.",
        tmp_path,
        extras={"runtime_seconds": 30, "use_llm": False},
    )
    assert r.ok
    assert (tmp_path / "agents" / "storyboard.json").is_file()
    assert any("llm=off" in n for n in r.notes)


def test_story_supervisor(tmp_path: Path):
    from agents.story_supervisor import STORY_SUPERVISOR_ID, run_story_supervisor
    from scene_ir import empty_scene_ir

    scene = empty_scene_ir(
        "Hero enters.\n\nThen finds the letter because light hits it.\n\nSteps forward."
    )
    report = run_story_supervisor(
        scene,
        brief=scene.user_prompt,
        extras={"runtime_seconds": 30, "style_id": "symmetrical_pastel_cinema"},
        style_profile={"style_id": "symmetrical_pastel_cinema"},
        job_dir=tmp_path,
    )
    assert report.auditor_id == STORY_SUPERVISOR_ID
    assert report.pack == "story"
    assert (tmp_path / "story_supervisor.json").is_file()


def test_write_story_props(tmp_path: Path):
    from tools.remotion_emitter import write_story_composition_props

    path = write_story_composition_props(
        tmp_path,
        storyboard={
            "shots": [
                {
                    "shot_id": 0,
                    "title": "A",
                    "action": "Walk in",
                    "duration_sec": 2.5,
                }
            ]
        },
        timing={"shots": [{"shot_id": 0, "duration_sec": 2.5, "duration_frames": 60}]},
    )
    assert path.is_file()
    assert "durationFrames" in path.read_text(encoding="utf-8")


def test_remotion_cli_resolves():
    from tools.remotion_emitter import _remotion_cli_cmd, remotion_ready

    if not remotion_ready():
        return
    cmd = _remotion_cli_cmd()
    assert cmd
    assert Path(cmd[0]).exists() or "npx" in Path(cmd[0]).name.lower()


def test_williams_bridge_optional(tmp_path: Path):
    from tools.williams_bridge import enrich_timing_with_williams

    timing = {"shots": [{"shot_id": 0, "duration_sec": 2.5}]}
    out = enrich_timing_with_williams(timing, job_dir=tmp_path)
    assert "shots" in out
    assert out["shots"][0].get("duration_sec") == 2.5
