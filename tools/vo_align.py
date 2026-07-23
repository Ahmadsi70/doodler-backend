"""
VO forced alignment — energy envelope (+ optional Whisper word timestamps).

Why: grapheme-uniform spacing drifts from real speech; energy peaks give
deterministic frame locks without a mandatory cloud ASR.
"""

from __future__ import annotations

import audioop
import wave
from pathlib import Path
from typing import Any, Literal

AlignMethod = Literal["energy", "whisper"]


def frame_energy(path: Path | str, *, fps: int = 24) -> list[float]:
    """Per-composition-frame RMS energy (0..1 normalized)."""
    p = Path(path)
    with wave.open(str(p), "rb") as w:
        rate = int(w.getframerate() or 1)
        width = int(w.getsampwidth() or 2)
        channels = int(w.getnchannels() or 1)
        raw = w.readframes(w.getnframes())
    if channels > 1:
        raw = audioop.tomono(raw, width, 0.5, 0.5)
    samples_per_frame = max(1, int(round(rate / fps)))
    bytes_per_sample = width
    frame_bytes = samples_per_frame * bytes_per_sample
    energies: list[float] = []
    for i in range(0, len(raw), frame_bytes):
        chunk = raw[i : i + frame_bytes]
        if len(chunk) < bytes_per_sample:
            break
        rms = float(audioop.rms(chunk, width))
        energies.append(rms)
    if not energies:
        return [0.0]
    peak = max(energies) or 1.0
    return [e / peak for e in energies]


def _tokenizeize_simple(text: str) -> list[tuple[str, str]]:
    from agents.phoneme_sync_agent import _tokenizeize

    return _tokenizeize(text)


def _try_whisper_words(path: Path, dialogue: str) -> list[dict[str, Any]] | None:
    """Optional Whisper word timestamps; returns None if unavailable."""
    try:
        import whisper  # type: ignore
    except ImportError:
        return None
    try:
        model = whisper.load_model("base")
        result = model.transcribe(str(path), word_timestamps=True, language="en")
    except Exception:  # noqa: BLE001
        return None
    words: list[dict[str, Any]] = []
    for seg in result.get("segments") or []:
        for w in seg.get("words") or []:
            words.append(
                {
                    "word": str(w.get("word") or "").strip(),
                    "start": float(w.get("start") or 0.0),
                    "end": float(w.get("end") or 0.0),
                }
            )
    if not words:
        return None
    # Keep dialogue for future mapping; whisper path still emits word-level shapes
    _ = dialogue
    return words


def align_dialogue_to_wav(
    dialogue: str,
    wav_path: Path | str,
    *,
    fps: int = 24,
    lead_frames: int = 2,
    speak_start: int = 0,
) -> list[dict[str, Any]]:
    """
    Forced-align dialogue tokens onto wav.

    Prefer Whisper word times when installed; else cumulative energy allocation.
    """
    path = Path(wav_path)
    lead = 1 if int(lead_frames) <= 1 else 2
    tokens = _tokenizeize_simple(dialogue)
    if not tokens:
        return []

    whisper_words = _try_whisper_words(path, dialogue)
    if whisper_words:
        out: list[dict[str, Any]] = []
        # Map tokens round-robin onto word midpoints
        for i, (token, shape) in enumerate(tokens):
            w = whisper_words[min(i, len(whisper_words) - 1)]
            mid = 0.5 * (float(w["start"]) + float(w["end"]))
            audio_f = speak_start + int(round(mid * fps))
            visual_f = max(0, audio_f - lead)
            out.append(
                {
                    "token": token,
                    "shape": shape,
                    "audio_frame": audio_f,
                    "visual_frame": visual_f,
                    "lead_frames": lead,
                    "method": "whisper",
                    "aligned": True,
                }
            )
        return out

    energy = frame_energy(path, fps=fps)
    # Voiced mask
    thr = max(0.12, 0.35 * (sum(energy) / max(1, len(energy))))
    voiced = [i for i, e in enumerate(energy) if e >= thr]
    if not voiced:
        voiced = list(range(len(energy)))
    # Cumulative energy on voiced frames for proportional allocation
    weights = [max(1e-6, energy[i]) for i in voiced]
    total_w = sum(weights)
    targets = len(tokens)
    # Assign each token a voiced frame by cumulative weight buckets
    out = []
    acc = 0.0
    ti = 0
    bucket = total_w / targets
    next_cut = bucket
    for wi, frame_i in enumerate(voiced):
        acc += weights[wi]
        while ti < targets and acc + 1e-9 >= next_cut:
            token, shape = tokens[ti]
            audio_f = speak_start + int(frame_i)
            visual_f = max(0, audio_f - lead)
            out.append(
                {
                    "token": token,
                    "shape": shape,
                    "audio_frame": audio_f,
                    "visual_frame": visual_f,
                    "lead_frames": lead,
                    "method": "energy",
                    "aligned": True,
                    "energy": float(energy[frame_i]),
                }
            )
            ti += 1
            next_cut += bucket
    # Remainder tokens at last voiced
    while ti < targets:
        token, shape = tokens[ti]
        audio_f = speak_start + int(voiced[-1])
        out.append(
            {
                "token": token,
                "shape": shape,
                "audio_frame": audio_f,
                "visual_frame": max(0, audio_f - lead),
                "lead_frames": lead,
                "method": "energy",
                "aligned": True,
            }
        )
        ti += 1
    return out
