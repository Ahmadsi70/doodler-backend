"""Gap-fix contracts: Continuity wiring, gate narrative, Light chapters, Williams."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BRIEF = (
    "Hero enters the quiet room.\n\n"
    "Then they notice a letter because sunlight hits the table.\n\n"
    "They step forward and breathe."
)


def test_continuity_loads_prompt_and_uses_cine():
    from agents.story_chain import run_cinematography, run_continuity, run_storyboard
    from tools.studio_router import load_agent_system_prompt, prompt_file_for_role

    assert prompt_file_for_role("continuity") == "continuity_agent.md"
    assert load_agent_system_prompt("continuity")
    board = run_storyboard(BRIEF, runtime_seconds=30)
    cine = run_cinematography(board)
    cont = run_continuity(board, cinematography=cine)
    assert cont["system_prompt_loaded"] is True
    assert "approved" in cont
    assert "violations" in cont
    assert "180_line_side" in cont
    assert len(cont.get("checks") or []) == len(board["shots"])


def test_supervisor_consumes_continuity(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain
    from agents.story_supervisor import run_story_supervisor
    from scene_ir import empty_scene_ir

    chain = run_story_agent_chain(
        BRIEF, tmp_path, extras={"runtime_seconds": 30, "use_llm": False}
    )
    report = run_story_supervisor(
        empty_scene_ir(BRIEF),
        brief=BRIEF,
        extras={"runtime_seconds": 30, "style_id": "symmetrical_pastel_cinema"},
        style_profile={"style_id": "symmetrical_pastel_cinema", "grade_preset": "pastel_muted"},
        job_dir=tmp_path,
        continuity=chain.continuity,
    )
    assert "continuity" in (report.craft or {})
    gate = report.pack_gate or {}
    # continuity evidence should reduce skips on 180 / screen direction when present
    assert gate.get("pack") == "story"


def test_remotion_props_include_style_and_continuity(tmp_path: Path):
    import json

    from tools.remotion_emitter import write_story_composition_props

    path = write_story_composition_props(
        tmp_path,
        storyboard={
            "shots": [
                {
                    "shot_id": 0,
                    "title": "A",
                    "action": "Walk",
                    "duration_sec": 2.5,
                }
            ]
        },
        cinematography={
            "frames": [{"shot_id": 0, "lens": "beauty", "camera": "motivated_push"}]
        },
        timing={"shots": [{"shot_id": 0, "duration_sec": 2.5, "duration_frames": 60}]},
        continuity={
            "180_line_side": "left",
            "approved": True,
            "violations": [],
        },
        style_profile={
            "style_id": "symmetrical_pastel_cinema",
            "engine": {"grade": "pastel_muted", "pace": "measured", "camera": "locked_symmetric"},
        },
        title="TestStory",
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props["grade"] == "pastel_muted"
    assert props["palette"]["bg0"]
    assert props["continuity"]["lineSide"] == "left"
    assert props["shots"][0]["camera"] == "motivated_push"


def test_story_gate_uses_narrative_close_not_shop_cta():
    from scene_ir import empty_scene_ir
    from tools.pack_quality_gate import build_evidence

    scene = empty_scene_ir(BRIEF)
    ev = build_evidence(
        scene,
        extras={
            "style_id": "symmetrical_pastel_cinema",
            "continuity": {
                "approved": True,
                "violations": [],
                "180_line_side": "left",
                "checks": [
                    {
                        "shot_id": 0,
                        "screen_direction": "L_to_R",
                        "eyeline": "consistent",
                        "cause_before_effect": True,
                    },
                    {
                        "shot_id": 1,
                        "screen_direction": "L_to_R",
                        "eyeline": "consistent",
                        "cause_before_effect": True,
                    },
                ],
            },
        },
        style_profile={"style_id": "symmetrical_pastel_cinema", "grade_preset": "pastel_muted"},
        pack="story",
    )
    assert ev["has_narrative_close"] is True
    assert ev["screen_direction_flips"] == 0
    assert ev["180_rule_violations"] == 0
    assert ev["cause_before_effect"] is True
    # Story must not require commercial CTA text
    assert ev.get("has_cta") is True  # mapped from narrative close for heuristics


def test_light_max_slides_allows_long_form():
    from runtime.light_slideshow import _split_slides

    many = "\n\n".join(f"Beat {i}." for i in range(20))
    assert len(_split_slides(many, max_slides=48)) == 20
    assert len(_split_slides(many, max_slides=12)) == 12


def test_manim_quarantined():
    from tools.manim_emitter import render_commercial

    try:
        render_commercial("x", Path("."), quality="light")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "Story" in str(exc) or "Remotion" in str(exc)


def test_williams_sets_anticipation(tmp_path: Path):
    from tools.williams_bridge import enrich_timing_with_williams

    out = enrich_timing_with_williams(
        {"shots": [{"shot_id": 0, "duration_sec": 3.0}]},
        job_dir=tmp_path,
    )
    if out.get("williams_enriched"):
        shot = out["shots"][0]
        assert int(shot.get("anticipation_frames") or 0) >= 4
        assert int(shot.get("hold_frames") or 0) >= 8
        assert int(shot.get("duration_frames") or 0) >= 24


def test_no_dead_commercial_modules():
    assert not (ROOT / "runtime" / "manim_renderer.py").is_file()
    assert not (ROOT / "tools" / "ffmpeg_post.py").is_file()


def test_job_artifacts_story_only():
    import inspect

    from tools import job_status, job_workspace

    src = inspect.getsource(job_status.list_artifact_files)
    assert "commercial_scene" not in src
    assert "story_props.json" in src
    src2 = inspect.getsource(job_workspace.expected_artifacts)
    assert "usdc" not in src2


def test_props_include_thirds(tmp_path: Path):
    import json

    from tools.remotion_emitter import write_story_composition_props

    path = write_story_composition_props(
        tmp_path,
        storyboard={
            "shots": [{"shot_id": 0, "title": "A", "action": "Walk", "duration_sec": 2}]
        },
        cinematography={
            "frames": [{"shot_id": 0, "lens": "beauty", "camera": "static", "composition": "L"}]
        },
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props["shots"][0]["thirdsX"] == 0.33
    assert props["shots"][0]["lookSpace"] == "right"


def test_williams_character_rig(tmp_path: Path):
    from tools.williams_character_bridge import enrich_character_rig

    rig = enrich_character_rig(job_dir=tmp_path)
    assert rig.get("keyframes")
    assert (tmp_path / "williams_character.json").is_file() or not rig.get(
        "williams_character"
    )
    if rig.get("williams_character"):
        assert len(rig["keyframes"]) >= 4
        assert "pelvisY" in rig["keyframes"][0]["joints"]
