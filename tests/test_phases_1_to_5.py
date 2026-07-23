"""Phases 1–5: SceneIR frame fill, VO wav, board gates, git hygiene helpers, UI auth."""

from __future__ import annotations

import json
import os
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Phase 1 ──────────────────────────────────────────────────────────────


def test_apply_frame_artifacts_fills_performance_channels():
    from agents.contact_lock_agent import run_contact_lock_agent
    from agents.performance_chart_agent import run_performance_chart_agent
    from agents.phoneme_sync_agent import run_phoneme_sync_agent
    from scene_ir import empty_scene_ir
    from tools.scene_ir_builder import apply_frame_artifacts_to_scene_ir

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "action": "Walks.",
            "dialogue": "Hi!",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    lock = run_contact_lock_agent(shots, performance_chart=chart, fps=24)
    phon = run_phoneme_sync_agent(shots, fps=24)
    ir = empty_scene_ir("test")
    enriched = apply_frame_artifacts_to_scene_ir(
        ir,
        performance_chart=chart,
        contact_lock=lock,
        phoneme_sync=phon,
        compliance_frame={
            "flags": {
                "fps_ok": True,
                "line_180_ok": True,
                "eyeline_ok": True,
                "chart_present": True,
                "contact_present": True,
            },
            "passed": True,
        },
    )
    assert enriched.performance is not None
    assert len(enriched.performance.keyframes) >= 4
    assert enriched.performance.contacts
    assert enriched.performance.phonemes
    for p in enriched.performance.phonemes:
        assert p.visual_frame <= p.audio_frame
    assert enriched.compliance is not None
    assert enriched.compliance.fps_is_24 is True
    assert "frame_artifacts=1" in (enriched.notes or [])


def test_write_props_also_enriches_scene_ir(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="IR",
        shots=[
            ShotControl(
                action="Hero walks.",
                dialogue="Hello",
                story_beat="entrance",
                pose="walk",
                duration_sec=2,
            )
        ],
    )
    c = compile_studio_spec(spec)
    write_story_composition_props(
        tmp_path,
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
    )
    ir_path = tmp_path / "scene_ir.json"
    assert ir_path.is_file()
    data = json.loads(ir_path.read_text(encoding="utf-8"))
    perf = data.get("performance") or {}
    assert perf.get("contacts")
    assert perf.get("phonemes")
    assert len(perf.get("keyframes") or []) >= 4


# ── Phase 2 ──────────────────────────────────────────────────────────────


def _write_silent_wav(path: Path, *, seconds: float = 1.0, rate: int = 24000) -> Path:
    n = int(seconds * rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n)
    return path


def test_vo_duration_frames_and_phoneme_stretch(tmp_path: Path):
    from agents.phoneme_sync_agent import run_phoneme_sync_agent
    from tools.vo_audio import duration_frames_for_wav, sync_vo_to_remotion_public

    wav = _write_silent_wav(tmp_path / "line.wav", seconds=1.0)
    frames = duration_frames_for_wav(wav, fps=24)
    assert 22 <= frames <= 26  # ~24f for 1s

    shots = [
        {
            "shot_id": 0,
            "dialogue": "Oh no!",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "vo_path": str(wav),
            "vo_duration_frames": frames,
        }
    ]
    sync = run_phoneme_sync_agent(shots, fps=24, lead_frames=2)
    assert sync["active"]
    audios = [p["audio_frame"] for p in sync["phonemes"] if p["shape"] != "rest"]
    assert audios
    assert max(audios) < frames + 6  # within VO window (+ ant offset)

    rel = sync_vo_to_remotion_public(wav, shot_id=0)
    assert rel.startswith("audio/")
    assert (ROOT / "remotion" / "public" / rel).is_file()


def test_props_include_vo_event_when_wav(tmp_path: Path):
    from studio_spec import ShotControl, StudioAssets, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    wav = _write_silent_wav(tmp_path / "vo.wav", seconds=0.5)
    spec = StudioSpec(
        title="VO",
        shots=[
            ShotControl(
                action="Hero speaks.",
                dialogue="Hi",
                vo_path=str(wav),
                duration_sec=2,
                story_beat="decision",
            )
        ],
        assets=StudioAssets(),
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path / "job",
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    roles = {e.get("role") for e in props["audioTimeline"]["events"]}
    assert "vo" in roles
    assert props["phonemeSync"]["active"] is True


# ── Phase 3 ──────────────────────────────────────────────────────────────


def test_load_frame_supervision_from_props(tmp_path: Path):
    from tools.frame_supervision_ui import load_frame_supervision, supervision_table_rows

    props = {
        "frameGate": {"passed": True, "score": 1.0, "findings": []},
        "complianceFrame": {
            "passed": True,
            "flags": {"fps_ok": True, "line_180_ok": True},
            "findings": [],
        },
        "phonemeSync": {"active": True, "phonemes": [{"token": "a"}]},
        "contactLock": {"contacts": [{"kind": "foot_L"}]},
    }
    (tmp_path / "story_props.json").write_text(
        json.dumps(props), encoding="utf-8"
    )
    sup = load_frame_supervision(tmp_path)
    assert sup["frame_gate_passed"] is True
    assert sup["compliance_passed"] is True
    assert sup["phoneme_active"] is True
    rows = supervision_table_rows(sup)
    assert any(r["check"] == "FrameGate" for r in rows)


# ── Phase 4 ──────────────────────────────────────────────────────────────


def test_story_git_hygiene_helpers():
    from tools.story_git import story_root_gitignore_entries, recommend_story_git_init

    entries = story_root_gitignore_entries()
    assert "node_modules/" in entries
    assert "out/" in entries
    report = recommend_story_git_init(ROOT)
    assert report["root"] == str(ROOT.resolve())
    assert "gitignore_ok" in report


# ── Phase 5 ──────────────────────────────────────────────────────────────


def test_ui_auth_gate():
    from tools.ui_auth import check_ui_password, ui_auth_required

    old = os.environ.get("STORY_UI_PASSWORD")
    try:
        os.environ.pop("STORY_UI_PASSWORD", None)
        assert ui_auth_required() is False
        assert check_ui_password("") is True
        os.environ["STORY_UI_PASSWORD"] = "secret"
        assert ui_auth_required() is True
        assert check_ui_password("wrong") is False
        assert check_ui_password("secret") is True
    finally:
        if old is None:
            os.environ.pop("STORY_UI_PASSWORD", None)
        else:
            os.environ["STORY_UI_PASSWORD"] = old


def test_colab_doc_exists():
    assert (ROOT / "docs" / "COLAB.md").is_file()
    assert (ROOT / "notebooks" / "story_colab.ipynb").is_file()
