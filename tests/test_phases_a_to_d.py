"""Phases A–D: VO align, CI helpers, board VO UI helpers, cinematic look/blink."""

from __future__ import annotations

import json
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_tone_wav(path: Path, *, seconds: float = 1.0, rate: int = 24000) -> Path:
    """Quiet → loud → quiet so energy align has structure."""
    n = int(seconds * rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for i in range(n):
        # envelope peaks in middle third
        t = i / max(1, n - 1)
        env = 0.15
        if 0.25 <= t <= 0.75:
            env = 0.9
        # crude square-ish tone
        sample = int(12000 * env) if (i // 40) % 2 == 0 else int(-12000 * env)
        frames += struct.pack("<h", max(-32767, min(32767, sample)))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


# ── A ─────────────────────────────────────────────────────────────────────


def test_vo_align_places_phonemes_on_energy(tmp_path: Path):
    from tools.vo_align import align_dialogue_to_wav, frame_energy

    wav = _write_tone_wav(tmp_path / "vo.wav", seconds=1.0)
    energy = frame_energy(wav, fps=24)
    assert len(energy) >= 20
    assert max(energy) > min(energy)

    marks = align_dialogue_to_wav("Oh no!", wav, fps=24, lead_frames=2)
    assert marks
    assert marks[0]["method"] in {"energy", "whisper"}
    for m in marks:
        assert m["visual_frame"] <= m["audio_frame"]
        assert m["audio_frame"] - m["visual_frame"] <= 2


def test_phoneme_sync_uses_align_when_vo_present(tmp_path: Path):
    from agents.phoneme_sync_agent import run_phoneme_sync_agent

    wav = _write_tone_wav(tmp_path / "line.wav", seconds=1.0)
    out = run_phoneme_sync_agent(
        [
            {
                "shot_id": 0,
                "dialogue": "Hello",
                "vo_path": str(wav),
                "duration_frames": 48,
                "anticipation_frames": 4,
            }
        ],
        fps=24,
        lead_frames=2,
    )
    assert out["active"]
    assert out.get("align_method") in {"energy", "whisper"}
    assert any(p.get("aligned") for p in out["phonemes"])


# ── B ─────────────────────────────────────────────────────────────────────


def test_ci_local_checklist_exists():
    from tools.ci_local import ci_local_plan

    plan = ci_local_plan(ROOT)
    assert plan["steps"]
    assert any("pytest" in s["cmd"] for s in plan["steps"])
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()
    assert (ROOT / "docs" / "GITHUB.md").is_file()


# ── C ─────────────────────────────────────────────────────────────────────


def test_phoneme_rows_for_board():
    from tools.frame_supervision_ui import phoneme_table_rows

    props = {
        "phonemeSync": {
            "active": True,
            "phonemes": [
                {
                    "shot_id": 0,
                    "token": "o",
                    "shape": "O",
                    "audio_frame": 10,
                    "visual_frame": 8,
                },
                {
                    "shot_id": 1,
                    "token": "a",
                    "shape": "A",
                    "audio_frame": 5,
                    "visual_frame": 3,
                },
            ],
        }
    }
    rows = phoneme_table_rows(props, shot_id=0)
    assert len(rows) == 1
    assert rows[0]["shape"] == "O"


def test_update_shot_manual_dialogue_and_vo(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.director_board import DirectorBoard, update_shot_manual

    board = DirectorBoard(
        spec=StudioSpec(
            title="C",
            shots=[ShotControl(action="Speaks.", duration_sec=2)],
        ),
        status="designed",
        approved=False,
        brief="x",
    )
    wav = _write_tone_wav(tmp_path / "v.wav", seconds=0.5)
    board = update_shot_manual(
        board,
        0,
        {"dialogue": "Hi there", "vo_path": str(wav)},
        job_dir=tmp_path,
    )
    assert board.spec.shots[0].dialogue == "Hi there"
    assert board.spec.shots[0].vo_path == str(wav)


# ── D ─────────────────────────────────────────────────────────────────────


def test_look_bible_has_stronger_grain_and_lut():
    from tools.craft_packs import look_for_beat

    look = look_for_beat("reaction")
    assert look["grain"] >= 0.1
    assert look.get("lutStrength", 0) >= 0.15
    assert "contrast" in look


def test_props_include_blink_and_look_cinematic(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="D",
        shots=[
            ShotControl(
                action="Walks in.",
                story_beat="entrance",
                pose="walk",
                duration_sec=2,
            ),
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
    s0 = props["shots"][0]
    assert s0.get("blinkEveryFrames", 0) >= 24
    assert s0["look"]["grain"] >= 0.05
    assert s0["look"].get("lutStrength") is not None
    assert s0.get("envProfile", {}).get("depthLayers") or s0["envProfile"].get("parallax")
