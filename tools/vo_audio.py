"""
VO audio helpers — duration in frames + sync wav into Remotion public.

Why: PhonemeSync needs real VO length; grapheme spacing alone drifts from audio.
"""

from __future__ import annotations

import shutil
import wave
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_REMOTION_AUDIO = _ROOT / "remotion" / "public" / "audio"


def duration_frames_for_wav(path: Path | str, *, fps: int = 24) -> int:
    """Return ceil(duration_sec * fps) from a PCM wav."""
    p = Path(path)
    with wave.open(str(p), "rb") as w:
        rate = int(w.getframerate() or 1)
        n = int(w.getnframes() or 0)
    seconds = n / max(1, rate)
    return max(1, int(round(seconds * fps)))


def sync_vo_to_remotion_public(path: Path | str, *, shot_id: Any = 0) -> str:
    """Copy VO wav → remotion/public/audio/vo_shot_{id}.wav; return relative path."""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"VO wav missing: {src}")
    _REMOTION_AUDIO.mkdir(parents=True, exist_ok=True)
    dest = _REMOTION_AUDIO / f"vo_shot_{shot_id}{src.suffix.lower() or '.wav'}"
    shutil.copy2(src, dest)
    return f"audio/{dest.name}"


def vo_audio_event(
    *,
    shot_id: Any,
    start_frame: int,
    file_rel: str,
    duration_frames: int | None = None,
    gain_db: float = -4.0,
) -> dict[str, Any]:
    """Remotion audioTimeline event for spoken VO."""
    return {
        "cue": f"vo_shot_{shot_id}",
        "file": file_rel,
        "startFrame": int(start_frame),
        "durationFrames": duration_frames,
        "shotId": shot_id,
        "gainDb": float(gain_db),
        "loop": False,
        "role": "vo",
    }
