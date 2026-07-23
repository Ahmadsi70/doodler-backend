"""Tests for AnimationPromptAgent — motion/I2V prompts for external tools."""

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
        title="نامهٔ سحر",
        style_id="ink_bw_editorial",
        grade="bw_graphic",
        emotion="sad",
        pace="measured",
        runtime_seconds=20,
        shots=[
            ShotControl(
                title="ورود",
                action="پسرک با کوله وارد ایستگاه متروکه می‌شود.",
                duration_sec=8,
                pose="walk",
                story_beat="entrance",
                camera="pan_follow",
                shot_size="WS",
                anticipation_frames=8,
                hold_frames=12,
            ),
            ShotControl(
                title="کشف",
                action="جعبه را باز می‌کند و نامه را می‌بیند.",
                duration_sec=10,
                pose="react",
                expression="sad",
                story_beat="reaction",
                camera="motivated_push",
                shot_size="CU",
                anticipation_frames=6,
                hold_frames=14,
            ),
        ],
    )


def _compiled(spec: StudioSpec):
    from tools.studio_api import compile_studio_spec

    return compile_studio_spec(spec)


def test_animation_prompt_agent_motion_fields():
    from agents.animation_prompt_agent import run_animation_prompt_agent

    c = _compiled(_spec())
    out = run_animation_prompt_agent(
        _spec(),
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
    )
    assert out["version"] == "1"
    assert len(out["shots"]) == 2
    s0 = out["shots"][0]
    assert s0["id"] == "shot_00"
    assert s0["motion_prompt"]
    assert "walk" in s0["motion_prompt"].lower() or "راه" in s0["motion_prompt"]
    assert s0["motion_json"]["duration_sec"] == 8
    assert "camera" in s0["motion_json"]
    assert "by_tool" in s0
    assert "runway" in s0["by_tool"]
    assert "kling" in s0["by_tool"]


def test_animation_prompt_uses_style_traits():
    from agents.animation_prompt_agent import run_animation_prompt_agent

    c = _compiled(_spec())
    out = run_animation_prompt_agent(
        _spec(),
        cinematography=c.cinematography,
        timing=c.timing,
    )
    joined = " ".join(s["motion_prompt"] for s in out["shots"])
    assert "ink" in joined.lower() or "editorial" in joined.lower() or "bw" in joined.lower()


def test_export_bundle_writes_motion_files(tmp_path):
    from tools.animation_export import export_animation_bundle

    root = Path(
        export_animation_bundle(_spec(), tmp_path / "b", targets=["prompts"])["export_root"]
    )
    assert (root / "prompts" / "shot_00_motion.txt").is_file()
    assert (root / "prompts" / "shot_00_motion.json").is_file()
    assert (root / "prompts" / "film_motion.txt").is_file()
    assert (root / "prompts" / "motion_guide.md").is_file()
    mj = json.loads((root / "prompts" / "shot_01_motion.json").read_text(encoding="utf-8"))
    assert mj.get("beat") == "reaction"
    assert (root / "prompts" / "tools" / "runway" / "shot_00.txt").is_file()


def test_export_preview_includes_motion():
    from tools.animation_export import build_export_preview

    prev = build_export_preview(_spec())
    assert "shot_motions" in prev
    assert "shot_00" in prev["shot_motions"]
