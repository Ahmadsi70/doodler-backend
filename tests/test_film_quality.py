"""Film-quality remaining priorities: look/cine/audio/performance/layers/context/gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_look_per_shot_on_props(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="Look",
        grade="pastel_muted",
        shots=[
            ShotControl(action="Enter.", story_beat="entrance", duration_sec=2),
            ShotControl(
                action="Fight.",
                story_beat="conflict",
                pose="react",
                duration_sec=2,
            ),
        ],
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path,
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        style_profile={"engine": {"grade": "pastel_muted"}},
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props["shots"][0].get("look")
    assert props["shots"][0]["look"]["gradeId"]
    assert props["shots"][1]["look"]["gradeId"] == "cold_tension"
    assert props["shots"][0]["look"]["palette"]["bg0"] != props["shots"][1]["look"]["palette"]["bg0"]


def test_cine_shot_size_and_expanded_camera():
    from studio_spec import ShotControl, StudioSpec

    sh = ShotControl(
        action="Close on face.",
        shot_size="CU",
        camera="pan_follow",
        lens="beauty",
        story_beat="reaction",
        duration_sec=2,
    )
    spec = StudioSpec(title="Cine", shots=[sh])
    assert spec.shots[0].shot_size == "CU"
    assert spec.shots[0].camera == "pan_follow"


def test_props_emit_shot_size_and_camera_move(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="CineProps",
        shots=[
            ShotControl(
                action="Reveal wide.",
                story_beat="reveal",
                shot_size="WS",
                camera="reveal_drift",
                duration_sec=2,
            )
        ],
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path,
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    shot = props["shots"][0]
    assert shot.get("shotSize") == "WS"
    assert shot["cameraMove"]["id"] in {"reveal_drift", "motivated_push", "pan_follow", "static"}


def test_performance_bible_has_blink_and_rich_walk():
    from tools.pose_presets import bake_shot_rig, load_performance_bible

    bible = load_performance_bible()
    walk = bible["poses"]["walk"]
    assert walk.get("blink_every_frames")
    assert len(walk["phases"]) >= 5
    rig = bake_shot_rig(pose="walk", expression="shock", fps=24)
    assert len(rig["keyframes"]) >= 5
    assert rig["expression"]["emotion"] == "shock"


def test_audio_import_and_bed_events(tmp_path: Path):
    import wave

    from tools.audio_cues import (
        build_audio_timeline,
        ensure_audio_cue_files,
        import_cue_wav,
    )

    ensure_audio_cue_files()
    custom = tmp_path / "custom_step.wav"
    srcs = list((ROOT / "libraries" / "audio" / "files").glob("foley_footstep_*.wav"))
    assert srcs, "expected Kenney footstep wavs"
    custom.write_bytes(srcs[0].read_bytes())
    dest = import_cue_wav("foley_footstep", custom)
    assert dest.is_file()
    with wave.open(str(dest), "rb") as w:
        assert w.getnframes() > 0

    tl = build_audio_timeline(
        [
            {"shotId": 0, "storyBeat": "entrance", "durationFrames": 48},
            {"shotId": 1, "storyBeat": "conflict", "durationFrames": 48},
        ],
        fps=24,
    )
    assert any(e.get("role") == "bed" for e in tl["events"])
    assert any("footstep" in str(e.get("cue")) for e in tl["events"])


def test_context_pack_injected_into_story_chain_extras(tmp_path: Path, monkeypatch):
    from agents import story_chain as sc

    monkeypatch.setattr(
        "agents.llm_enrich.llm_enabled",
        lambda extras=None: True,
    )

    called: dict = {}

    def fake_enrich(brief, storyboard, *, context_block=None):
        called["context_block"] = context_block
        return None

    monkeypatch.setattr("agents.llm_enrich.enrich_storyboard_llm", fake_enrich)

    result = sc.run_story_agent_chain(
        "Enter.\n\nThen shock because fire.\n\nExit.",
        tmp_path,
        extras={"runtime_seconds": 18, "use_llm": True, "inject_context_pack": True},
    )
    assert result.ok
    assert (tmp_path / "compressed_context.json").is_file()
    assert called.get("context_block")
    assert "BIBLE" in called["context_block"] or "ACT" in called["context_block"]


def test_continuity_gate_blocks_when_strict():
    from tools.continuity_graph import build_continuity_graph, continuity_gate

    storyboard = {
        "shots": [
            {"shot_id": 0, "story_beat": "entrance", "composition_shape": "L", "pose": "walk"},
            {"shot_id": 1, "story_beat": "exit", "composition_shape": "R", "pose": "walk"},
        ]
    }
    cine = {
        "frames": [
            {"shot_id": 0, "composition": "L", "look_space_direction": "right"},
            {"shot_id": 1, "composition": "R", "look_space_direction": "left"},
        ]
    }
    graph = build_continuity_graph(
        storyboard=storyboard,
        cinematography=cine,
        continuity={"approved": True, "180_line_side": "left"},
    )
    soft = continuity_gate(graph, strict=False)
    assert soft["ok"] is True
    hard = continuity_gate(graph, strict=True)
    # direction flip should fail strict
    assert hard["ok"] is False
    assert hard["violations"]
