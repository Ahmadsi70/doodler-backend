"""Next-step features: audio cues, act-batch render, layered character."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ensure_audio_cue_files_writes_wavs():
    from tools.audio_cues import ensure_audio_cue_files, load_cues_manifest

    paths = ensure_audio_cue_files()
    assert paths
    for p in paths.values():
        assert Path(p).is_file()
        with wave.open(str(p), "rb") as w:
            assert w.getnframes() > 0
    man = load_cues_manifest()
    assert man["cues"]["foley_footstep"]["file"]


def test_audio_timeline_for_shots():
    from tools.audio_cues import build_audio_timeline

    shots = [
        {"shotId": 0, "storyBeat": "entrance", "durationFrames": 48},
        {"shotId": 1, "storyBeat": "reaction", "durationFrames": 36},
    ]
    tl = build_audio_timeline(shots, fps=24)
    assert tl["schema"] == "audio_timeline#v1"
    cues = {e["cue"] for e in tl["events"]}
    assert any("footstep" in c for c in cues)
    assert any("hit" in c or "soft" in c for c in cues)

def test_props_include_audio_timeline(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="Audio",
        shots=[
            ShotControl(action="Enter.", story_beat="entrance", pose="walk", duration_sec=2),
            ShotControl(
                action="Shock.",
                story_beat="reaction",
                pose="react",
                expression="shock",
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
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert "audioTimeline" in props
    assert props["audioTimeline"]["events"]
    pub = ROOT / "remotion" / "public" / "audio"
    assert any(pub.glob("*.wav")), "expected cue wavs copied to remotion/public/audio"


def test_act_batch_render_mock(tmp_path: Path, monkeypatch):
    from studio_spec import ShotControl, StudioSpec
    import tools.act_render as act_render

    spec = StudioSpec(
        title="Acts",
        runtime_seconds=30,
        quality="light",
        shots=[
            ShotControl(action=f"A{i}", duration_sec=3, story_beat="decision")
            for i in range(6)
        ],
    )
    calls: list[str] = []

    def fake_render(s, *, job_id=None, workspace=None, on_event=None):
        calls.append(str(workspace))
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "render.mp4").write_bytes(b"\x00" * 64)
        return {"ok": True, "rendered": True, "artifacts": {"render_mp4": str(ws / "render.mp4")}}

    monkeypatch.setattr(act_render, "render_from_spec", fake_render)
    monkeypatch.setattr(
        act_render,
        "concat_mp4s",
        lambda parts, dest, *, ffmpeg: Path(dest).write_bytes(b"\x00" * 128) or Path(dest),
    )
    monkeypatch.setattr(act_render, "find_ffmpeg", lambda: "ffmpeg")

    result = act_render.render_spec_by_acts(
        spec,
        workspace=tmp_path / "job",
        target_act_seconds=8.0,
    )
    assert result["ok"]
    assert result["act_count"] >= 2
    assert len(calls) == result["act_count"]
    assert Path(result["artifacts"]["render_mp4"]).is_file()


def test_layered_character_assets_on_props(tmp_path: Path):
    from PIL import Image

    from studio_spec import CharacterLayers, ShotControl, StudioAssets, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    layers_dir = tmp_path / "layers"
    layers_dir.mkdir()
    body = layers_dir / "body.png"
    head = layers_dir / "head.png"
    Image.new("RGBA", (40, 80), (80, 100, 120, 255)).save(body)
    Image.new("RGBA", (30, 30), (200, 160, 140, 255)).save(head)

    spec = StudioSpec(
        title="Layers",
        assets=StudioAssets(
            layers=CharacterLayers(body=str(body), head=str(head)),
        ),
        shots=[ShotControl(action="Stand.", pose="idle", duration_sec=2)],
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path / "out",
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
        character_layers=spec.assets.layers.model_dump(mode="json"),
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props.get("characterLayers")
    assert props["characterLayers"]["body"]
    pub = ROOT / "remotion" / "public" / "layers"
    assert (pub / "body.png").is_file() or Path(props["characterLayers"]["body"]).name == "body.png"


def test_director_board_act_rows(tmp_path: Path):
    from tools.act_planner import plan_acts
    from tools.director_board import act_table_rows, design_from_brief

    board = design_from_brief(
        "Enter.\n\nShock because fire.\n\nLeave.\n\nHold quiet.\n\nDecide.\n\nExit.",
        job_dir=tmp_path / "design_job",
        quality="light",
        runtime_seconds=24,
    )
    plan = plan_acts(board.spec, target_act_seconds=6.0)
    rows = act_table_rows(board.spec, plan)
    assert rows
    assert "shots" in rows[0]
