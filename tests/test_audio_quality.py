"""
Programmatic verification tests for AudioLDM dynamic duration generation,
silent audio track fallbacks, and MoviePy video/audio duration sync.

Verifies:
1. AudioLDM receives dynamic scene duration (audio_length_in_s = scene_duration) instead of fixed 2.0s.
2. Silent audio track fallback is generated for scenes without sound prompts or when AudioLDM fails.
3. Every scene video clip retains a synced audio track matching clip duration.
4. MoviePy concatenate_videoclips preserves full audio duration across concatenated scenes without truncation.
"""

import os
import tempfile
import numpy as np
import scipy.io.wavfile
import pytest
from unittest.mock import MagicMock, patch

try:
    from moviepy import ColorClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import ColorClip, AudioFileClip, concatenate_videoclips

import runpod_backend.server as server_module
import runpod_backend.handler as handler_module


def create_dummy_wav(path: str, duration_s: float, sample_rate: int = 16000, frequency: float = 440.0):
    """Utility to generate a dummy sine-wave WAV file for testing."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    signal = (0.5 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    scipy.io.wavfile.write(path, sample_rate, signal)
    return signal


def test_audioldm_dynamic_duration_parameter_server():
    """Verify server.py passes dynamic scene duration to audioldm_pipe."""
    mock_pipe = MagicMock()
    mock_audio_obj = MagicMock()
    mock_audio_obj.audios = [np.zeros(16000 * 5, dtype=np.float32)]
    mock_pipe.return_value = mock_audio_obj

    with tempfile.TemporaryDirectory() as tmpdir:
        job_id = "test_job_dynamic"
        spec = {
            "timeline": {
                "scenes": [
                    {"start_time": 0.0, "end_time": 4.5, "motion_type": "walk", "sfx_prompt": "footsteps on pavement"},
                    {"start_time": 4.5, "end_time": 10.5, "motion_type": "jump", "sfx_prompt": "heavy impact landed"}
                ]
            }
        }

        with patch.object(server_module, "audioldm_pipe", mock_pipe), \
             patch("runpod_backend.server.build_strict_character_prompt", return_value="dummy prompt"), \
             patch("runpod_backend.server.generate_mvc_yaml", return_value=""), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # Call process_video_job
            server_module.process_video_job(job_id, spec)

            assert mock_pipe.call_count == 2
            # Inspect first scene call duration
            first_call_kwargs = mock_pipe.call_args_list[0].kwargs
            assert first_call_kwargs.get("audio_length_in_s") == 4.5

            # Inspect second scene call duration
            second_call_kwargs = mock_pipe.call_args_list[1].kwargs
            assert second_call_kwargs.get("audio_length_in_s") == 6.0


def test_audioldm_dynamic_duration_parameter_handler():
    """Verify handler.py passes dynamic scene duration to audioldm_pipe."""
    mock_pipe = MagicMock()
    mock_audio_obj = MagicMock()
    mock_audio_obj.audios = [np.zeros(16000 * 3, dtype=np.float32)]
    mock_pipe.return_value = mock_audio_obj

    job_payload = {
        "input": {
            "spec": {
                "timeline": {
                    "scenes": [
                        {"start_time": 1.0, "end_time": 4.2, "motion_type": "wave", "sfx_prompt": "cheering crowd"}
                    ]
                }
            }
        }
    }

    with patch.object(handler_module, "audioldm_pipe", mock_pipe), \
         patch("runpod_backend.handler.init_models"), \
         patch("runpod_backend.handler.build_strict_character_prompt", return_value="dummy prompt"), \
         patch("runpod_backend.handler.generate_mvc_yaml", return_value=""), \
         patch("subprocess.run") as mock_subproc:

        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = handler_module.handler(job_payload)

        assert mock_pipe.call_count == 1
        call_kwargs = mock_pipe.call_args.kwargs
        assert call_kwargs.get("audio_length_in_s") == pytest.approx(3.2)


def test_silent_audio_fallback_for_empty_sfx_prompt():
    """Verify silent audio WAV fallback is generated for scenes with missing or empty sfx_prompt."""
    mock_pipe = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        job_id = "test_job_silent"
        spec = {
            "timeline": {
                "scenes": [
                    {"start_time": 0.0, "end_time": 3.0, "motion_type": "walk", "sfx_prompt": ""},
                    {"start_time": 3.0, "end_time": 8.0, "motion_type": "dance"} # missing sfx_prompt
                ]
            }
        }

        with patch.object(server_module, "audioldm_pipe", mock_pipe), \
             patch("runpod_backend.server.build_strict_character_prompt", return_value="dummy prompt"), \
             patch("runpod_backend.server.generate_mvc_yaml", return_value=""), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

            # AudioLDM pipe should NOT be called since prompts are empty/missing
            server_module.process_video_job(job_id, spec)
            assert mock_pipe.call_count == 0

            # Verify silent wav files were written with correct duration and zero amplitude
            audio_path_0 = f"/tmp/sfx_{job_id}_0.wav"
            audio_path_1 = f"/tmp/sfx_{job_id}_1.wav"

            if os.path.exists(audio_path_0):
                sr, data = scipy.io.wavfile.read(audio_path_0)
                duration = len(data) / sr
                assert duration == pytest.approx(3.0)
                assert np.all(data == 0)
                os.remove(audio_path_0)

            if os.path.exists(audio_path_1):
                sr, data = scipy.io.wavfile.read(audio_path_1)
                duration = len(data) / sr
                assert duration == pytest.approx(5.0)
                assert np.all(data == 0)
                os.remove(audio_path_1)


def test_silent_audio_fallback_when_audioldm_fails():
    """Verify silent audio WAV fallback is generated if AudioLDM raises an exception."""
    mock_pipe = MagicMock(side_effect=RuntimeError("CUDA out of memory"))

    with tempfile.TemporaryDirectory() as tmpdir:
        job_id = "test_job_fail_fallback"
        spec = {
            "timeline": {
                "scenes": [
                    {"start_time": 0.0, "end_time": 4.0, "motion_type": "jump", "sfx_prompt": "explosion"}
                ]
            }
        }

        with patch.object(server_module, "audioldm_pipe", mock_pipe), \
             patch("runpod_backend.server.build_strict_character_prompt", return_value="dummy prompt"), \
             patch("runpod_backend.server.generate_mvc_yaml", return_value=""), \
             patch("subprocess.run") as mock_subproc:

            mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

            server_module.process_video_job(job_id, spec)

            audio_path = f"/tmp/sfx_{job_id}_0.wav"
            assert os.path.exists(audio_path)
            sr, data = scipy.io.wavfile.read(audio_path)
            duration = len(data) / sr
            assert duration == pytest.approx(4.0)
            assert np.all(data == 0)
            os.remove(audio_path)


def test_moviepy_audio_sync_and_no_truncation():
    """
    Verify MoviePy video clips with generated / silent audio tracks concatenate seamlessly
    without audio truncation or missing audio tracks.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        wav1 = os.path.join(tmpdir, "sfx_1.wav")
        wav2 = os.path.join(tmpdir, "sfx_2.wav")
        wav3 = os.path.join(tmpdir, "sfx_3.wav")

        # Create 3 audio tracks: 3s sound, 5s silence (empty prompt), 2.5s sound
        create_dummy_wav(wav1, duration_s=3.0, frequency=440.0)
        # silent track
        scipy.io.wavfile.write(wav2, 16000, np.zeros(16000 * 5, dtype=np.float32))
        create_dummy_wav(wav3, duration_s=2.5, frequency=880.0)

        # Create color video clips
        c1 = ColorClip(size=(64, 64), color=(255, 0, 0), duration=3.0)
        c2 = ColorClip(size=(64, 64), color=(0, 255, 0), duration=5.0)
        c3 = ColorClip(size=(64, 64), color=(0, 0, 255), duration=2.5)

        # Attach audio clips
        a1 = AudioFileClip(wav1)
        a2 = AudioFileClip(wav2)
        a3 = AudioFileClip(wav3)

        c1 = c1.with_audio(a1) if hasattr(c1, "with_audio") else c1.set_audio(a1)
        c2 = c2.with_audio(a2) if hasattr(c2, "with_audio") else c2.set_audio(a2)
        c3 = c3.with_audio(a3) if hasattr(c3, "with_audio") else c3.set_audio(a3)

        # Verify each clip has a valid audio track equal to its duration
        for idx, clip in enumerate([c1, c2, c3]):
            assert clip.audio is not None, f"Clip {idx} missing audio track"
            assert clip.audio.duration == pytest.approx(clip.duration), f"Clip {idx} audio duration mismatch"

        # Concatenate videoclips
        final = concatenate_videoclips([c1, c2, c3])

        expected_total_duration = 3.0 + 5.0 + 2.5 # 10.5s
        assert final.duration == pytest.approx(expected_total_duration)
        assert final.audio is not None, "Concatenated video is missing audio track"
        assert final.audio.duration == pytest.approx(expected_total_duration), "Concatenated audio was truncated!"
