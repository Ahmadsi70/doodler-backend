"""Long-form chapter batching + FFmpeg concat."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from tools.chapter_concat import chunk_shots, concat_mp4s
from tools.studio_profiles import find_ffmpeg


def test_chunk_shots():
    shots = [{"shot_id": i} for i in range(25)]
    batches = chunk_shots(shots, batch_size=12)
    assert len(batches) == 3
    assert len(batches[0]) == 12
    assert len(batches[2]) == 1


@pytest.mark.skipif(not find_ffmpeg(), reason="ffmpeg required")
def test_light_concat_backend(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANIMATION_DETERMINISTIC_SLIDES", "1")
    from tools.remotion_emitter import render_story

    brief = "\n\n".join(f"Beat number {i} happens now." for i in range(14))
    storyboard = {
        "shots": [
            {
                "shot_id": i,
                "title": f"Shot {i}",
                "action": f"Beat {i}",
                "duration_sec": 2.0,
            }
            for i in range(14)
        ]
    }
    art = render_story(
        brief,
        tmp_path,
        quality="light",
        prefer_remotion=False,
        ffmpeg=find_ffmpeg(),
        storyboard=storyboard,
    )
    assert art.get("backend") == "light_slideshow_concat"
    assert int(art.get("batches") or 0) == 2
    mp4 = Path(str(art["render_mp4"]))
    assert mp4.is_file() and mp4.stat().st_size > 0
    assert len(art.get("parts") or []) == 2


@pytest.mark.skipif(not find_ffmpeg(), reason="ffmpeg required")
def test_concat_mp4s_single(tmp_path: Path):
    # Minimal: create tiny mp4 via ffmpeg color source
    ff = find_ffmpeg()
    assert ff
    part = tmp_path / "a.mp4"
    dest = tmp_path / "out.mp4"
    import subprocess

    subprocess.run(
        [
            ff,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=0.5",
            "-pix_fmt",
            "yuv420p",
            str(part),
        ],
        check=True,
        capture_output=True,
    )
    out = concat_mp4s([part], dest, ffmpeg=ff)
    assert out.is_file()
