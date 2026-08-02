"""TDD: educational narration layer (edge-tts cues + ffmpeg mux)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from libraries.edu_narration import (
    NarrationCue,
    build_narration_plan,
    mux_video_with_narration,
    synthesize_cues,
)
from libraries.storybook_scene_pack import WATER_CYCLE_KIDS, plan_from_scene_pack


def test_water_cycle_pack_has_five_narrated_scenes() -> None:
    plan = plan_from_scene_pack(WATER_CYCLE_KIDS, target_sec=40.0)
    assert len(plan.pages) == 5
    assert all((p.narration or "").strip() for p in plan.pages)
    assert plan.language == "en"
    assert all(not any("\u0600" <= ch <= "\u06ff" for ch in (p.narration or "")) for p in plan.pages)
    assert "watercolor" in plan.style_lock.lower()
    assert "dropi" in plan.character_bible.lower()


def test_build_narration_plan_orders_cues() -> None:
    cues = build_narration_plan(
        [
            ("Sun warms the lake.", 6.0),
            ("Water becomes vapor.", 7.0),
            ("Clouds form.", 5.0),
        ]
    )
    assert len(cues) == 3
    assert cues[0].start_sec == 0.0
    assert cues[1].start_sec == 6.0
    assert cues[2].start_sec == 13.0
    assert cues[-1].end_sec == 18.0


def test_build_narration_plan_keeps_offline_fallback_text() -> None:
    """SAPI-only machines need Latin fallback when Persian neural TTS is offline."""
    cues = build_narration_plan(
        [
            ("آب در دریاچه آرام است.", 6.0, "Water rests calmly in the lake."),
        ]
    )
    assert cues[0].text.startswith("آب")
    assert cues[0].fallback_text.startswith("Water")


def test_synthesize_uses_fallback_when_primary_tts_empty(tmp_path: Path) -> None:
    cues = build_narration_plan(
        [("فارسی", 2.0, "Hello drop friends.")]
    )
    calls: list[str] = []

    def _fake_tts(text: str, out: Path) -> None:
        calls.append(text)
        # Simulate English-only SAPI: Persian yields tiny wav; English works.
        if any("\u0600" <= ch <= "\u06ff" for ch in text):
            out.write_bytes(b"RIFF" + b"\x00" * 42)
            return
        out.write_bytes(b"0" * 800)

    with patch("libraries.edu_narration.shutil.which", return_value="ffmpeg"), patch(
        "libraries.edu_narration.subprocess.run"
    ) as run, patch(
        "libraries.edu_narration._probe_duration_sec", return_value=1.5
    ):
        def _side_effect(cmd, **_k):
            # Final mix write
            if isinstance(cmd, list) and any(
                str(x).endswith("narration_mix.mp3") for x in cmd
            ):
                Path(cmd[-1]).write_bytes(b"1" * 600)
            return MagicMock(returncode=0, stderr="", stdout="")

        run.side_effect = _side_effect
        report = synthesize_cues(cues, tmp_path, synthesize_fn=_fake_tts)

    assert report["ok"] is True
    assert calls == ["فارسی", "Hello drop friends."]
    assert Path(report["mix_mp3"]).is_file()


def test_water_cycle_pack_has_english_offline_narration() -> None:
    assert all((c.narration_en or "").strip() for c in WATER_CYCLE_KIDS.scenes)


def test_mux_calls_ffmpeg(tmp_path: Path) -> None:
    video = tmp_path / "silent.mp4"
    audio = tmp_path / "voice.mp3"
    out = tmp_path / "final_narrated.mp4"
    video.write_bytes(b"0" * 200)
    audio.write_bytes(b"0" * 200)
    with patch("libraries.edu_narration.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        # Pretend ffmpeg wrote the file
        def _side_effect(*_a, **_k):
            out.write_bytes(b"1" * 300)
            return MagicMock(returncode=0)

        run.side_effect = _side_effect
        report = mux_video_with_narration(video, audio, out)
    assert report["ok"] is True
    assert run.called
    cmd = run.call_args.args[0]
    assert "ffmpeg" in cmd[0]
    assert str(video) in cmd
    assert str(audio) in cmd
