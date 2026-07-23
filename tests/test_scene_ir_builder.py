"""SceneIR must be filled from agent chain, not left empty."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = (
    "Hero enters.\n\n"
    "Then reacts in shock because fire.\n\n"
    "Leaves quietly."
)


def test_build_scene_ir_from_chain_has_shots_and_camera(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain
    from tools.scene_ir_builder import build_scene_ir_from_chain

    chain = run_story_agent_chain(
        BRIEF, tmp_path, extras={"runtime_seconds": 24, "use_llm": False}
    )
    ir = build_scene_ir_from_chain(
        BRIEF,
        storyboard=chain.storyboard,
        cinematography=chain.cinematography,
        timing=chain.animation_timing,
        continuity=chain.continuity,
        job_out_dir=str(tmp_path),
    )
    assert ir.shot_list is not None
    assert len(ir.shot_list.shots) >= 3
    assert ir.camera_plan is not None
    assert len(ir.camera_plan.keyframes) >= 3
    assert ir.story_brief is not None
    assert ir.story_brief.beats
    assert ir.compliance is not None
    assert ir.compliance.fps_is_24 is True
    path = tmp_path / "scene_ir.json"
    path.write_text(ir.model_dump_json(indent=2), encoding="utf-8")
    assert path.is_file()
