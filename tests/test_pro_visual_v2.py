"""Pro visual v2: craft rig pose on props + pose joint presets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = (
    "Hero enters the hall.\n\n"
    "Then they react in shock because the letter burns.\n\n"
    "They leave into the dark."
)


def test_pose_presets_differ_by_pose():
    from tools.pose_presets import expression_channels, joints_for_pose

    walk = joints_for_pose("walk", "neutral")
    react = joints_for_pose("react", "shock")
    idle = joints_for_pose("idle", "neutral")
    assert walk["leftLegStride"] != idle["leftLegStride"] or walk["rightLegStride"] != 0
    assert abs(react["shouldersRotZ"]) > abs(idle["shouldersRotZ"])
    shock = expression_channels("shock")
    assert shock["eyesOpen"] < 1.0
    assert shock["brows"] != 0


def test_pro_props_include_env_and_shot_rig(tmp_path: Path):
    from agents.story_chain import run_story_agent_chain
    from tools.remotion_emitter import write_story_composition_props

    chain = run_story_agent_chain(
        BRIEF, tmp_path, extras={"runtime_seconds": 24, "use_llm": False}
    )
    path = write_story_composition_props(
        tmp_path,
        storyboard=chain.storyboard,
        cinematography=chain.cinematography,
        timing=chain.animation_timing,
        continuity=chain.continuity,
        style_profile={
            "style_id": "symmetrical_pastel_cinema",
            "engine": {"grade": "pastel_muted", "pace": "measured"},
        },
        title="VisualV2",
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props.get("visualVersion") >= 2
    assert len(props["shots"]) >= 3
    with_pose = [
        s
        for s in props["shots"]
        if (s.get("craftHints") or {}).get("rig", {}).get("pose")
    ]
    assert with_pose, "expected craftHints.rig.pose on shots"
    with_env = [s for s in props["shots"] if s.get("envProfile")]
    assert with_env, "expected envProfile per shot"
    with_shot_rig = [s for s in props["shots"] if s.get("shotRig")]
    assert with_shot_rig, "expected per-shot rig pose bake"
    react = next(
        (s for s in props["shots"] if s.get("storyBeat") == "reaction"),
        with_pose[0],
    )
    assert react["envProfile"]["mood"] in {"tense", "drama", "neutral", "soft", "exit"}
