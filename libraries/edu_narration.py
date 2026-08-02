"""
Educational narration layer — TTS cues + ffmpeg mux onto storybook MP4.

Why: keep Story visuals for meaning; add explainer-style voice without
replacing the painting pipeline (layered architecture).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class NarrationCue:
    """One spoken beat aligned to a page hold window."""

    index: int
    text: str
    start_sec: float
    end_sec: float
    # Latin/offline line when neural Persian TTS cannot run (e.g. English-only SAPI).
    fallback_text: str = ""

    @property
    def duration_sec(self) -> float:
        return max(0.0, float(self.end_sec) - float(self.start_sec))


def build_narration_plan(
    beats: Sequence[tuple[str, float] | tuple[str, float, str]],
) -> list[NarrationCue]:
    """
    Stack page holds into a timeline of narration windows.

    ``beats`` = (text, hold_sec) or (text, hold_sec, fallback_text) in order.
    """
    cues: list[NarrationCue] = []
    t = 0.0
    for i, beat in enumerate(beats):
        text = beat[0]
        hold = beat[1]
        fallback = beat[2] if len(beat) >= 3 else ""
        hold_f = max(0.5, float(hold))
        cues.append(
            NarrationCue(
                index=i,
                text=(text or "").strip(),
                start_sec=round(t, 3),
                end_sec=round(t + hold_f, 3),
                fallback_text=(fallback or "").strip(),
            )
        )
        t += hold_f
    return cues


def _has_arabic_script(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))


def _tts_output_ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size >= 500


def _probe_duration_sec(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return max(0.0, float((proc.stdout or "").strip()))
    except ValueError:
        return 0.0


async def _edge_tts_save(text: str, out_mp3: Path, *, voice: str) -> None:
    import edge_tts

    comm = edge_tts.Communicate(text, voice=voice)
    await comm.save(str(out_mp3))


def _windows_sapi_save(text: str, out_mp3: Path) -> None:
    """
    Offline Windows SAPI fallback when edge-tts network is unavailable.

    Why script-file + size check: inline -Command mangles Unicode, and
    English-only Desktop voices write empty WAV headers for Persian text.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required for SAPI wav→mp3")
    speak = (text or "").strip()
    if not speak:
        raise RuntimeError("Windows SAPI failed: empty text")
    wav = out_mp3.with_suffix(".wav")
    wav.unlink(missing_ok=True)
    safe = speak.replace("'", "''")
    script = out_mp3.with_suffix(".sapi.ps1")
    script.write_text(
        (
            "Add-Type -AssemblyName System.Speech\n"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            f"$s.SetOutputToWaveFile('{str(wav.resolve())}')\n"
            f"$s.Speak('{safe}')\n"
            "$s.Dispose()\n"
        ),
        encoding="utf-8-sig",
    )
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        size = wav.stat().st_size if wav.is_file() else 0
        if proc.returncode != 0 or size < 500:
            detail = (proc.stderr or proc.stdout or "").strip()[:240]
            raise RuntimeError(
                f"Windows SAPI failed: wav_bytes={size}"
                + (f"; {detail}" if detail else " (no Persian Desktop voice?)")
            )
        conv = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(wav),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(out_mp3),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if conv.returncode != 0 or not _tts_output_ok(out_mp3):
            raise RuntimeError(f"wav→mp3 failed: {(conv.stderr or '')[-200:]}")
    finally:
        wav.unlink(missing_ok=True)
        script.unlink(missing_ok=True)


def synthesize_cues(
    cues: Sequence[NarrationCue],
    audio_dir: str | Path,
    *,
    voice: str = "fa-IR-DilaraNeural",
    synthesize_fn: Callable[[str, Path], None] | None = None,
) -> dict[str, Any]:
    """
    Write per-cue MP3s and one concatenated timeline WAV/MP3 via ffmpeg.

    Falls back to empty silent track segments when TTS is unavailable.
    """
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    meta: list[dict[str, Any]] = []

    for cue in cues:
        part = audio_dir / f"cue_{cue.index:02d}.mp3"
        if not cue.text:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg not found on PATH")
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    f"{max(0.5, cue.duration_sec):.3f}",
                    "-q:a",
                    "9",
                    str(part),
                ],
                capture_output=True,
                check=False,
            )
            parts.append(part)
            meta.append({"index": cue.index, "path": str(part), "empty": True})
            continue
        backend = "inject"
        spoken = cue.text
        used_fallback = False
        if synthesize_fn is not None:
            synthesize_fn(spoken, part)
            if not _tts_output_ok(part) and cue.fallback_text:
                part.unlink(missing_ok=True)
                spoken = cue.fallback_text
                synthesize_fn(spoken, part)
                used_fallback = True
            backend = "inject"
        else:
            try:
                asyncio.run(_edge_tts_save(spoken, part, voice=voice))
                backend = "edge-tts"
            except Exception:  # noqa: BLE001
                # Network/DNS often blocks edge-tts; keep lesson pipeline green.
                try_text = spoken
                if _has_arabic_script(spoken) and cue.fallback_text:
                    # English-only SAPI cannot phonate Persian → empty WAV.
                    try_text = cue.fallback_text
                    used_fallback = True
                _windows_sapi_save(try_text, part)
                spoken = try_text
                backend = "windows-sapi"
        if not _tts_output_ok(part):
            raise RuntimeError(f"TTS produced empty audio for cue {cue.index}")
        parts.append(part)
        dur = _probe_duration_sec(part)
        meta.append(
            {
                "index": cue.index,
                "path": str(part),
                "tts_duration_sec": dur,
                "window_sec": cue.duration_sec,
                "backend": backend,
                "spoken_text": spoken,
                "used_fallback": used_fallback,
            }
        )

    # Build a single narration track: pad/trim each cue into its hold window.
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")

    # filter: for each cue, atrim/apad to window, then concat
    filter_parts: list[str] = []
    inputs: list[str] = [ffmpeg, "-y"]
    for i, cue in enumerate(cues):
        inputs.extend(["-i", str(parts[i])])
        win = max(0.5, cue.duration_sec)
        # apad then atrim to exact window
        filter_parts.append(
            f"[{i}:a]apad=pad_dur={win:.3f},atrim=0:{win:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_in = "".join(f"[a{i}]" for i in range(len(cues)))
    filter_complex = (
        ";".join(filter_parts)
        + f";{concat_in}concat=n={len(cues)}:v=0:a=1[aout]"
    )
    mixed = audio_dir / "narration_mix.mp3"
    cmd = [
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(mixed),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not mixed.is_file():
        raise RuntimeError(
            f"ffmpeg narration mix failed: {(proc.stderr or '')[-400:]}"
        )

    cue_json = audio_dir / "narration_cues.json"
    cue_json.write_text(
        json.dumps(
            {
                "voice": voice,
                "cues": [
                    {
                        "index": c.index,
                        "text": c.text,
                        "start_sec": c.start_sec,
                        "end_sec": c.end_sec,
                    }
                    for c in cues
                ],
                "parts": meta,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "mix_mp3": str(mixed),
        "cues_json": str(cue_json),
        "n_cues": len(cues),
    }


def mux_video_with_narration(
    video_mp4: str | Path,
    narration_mp3: str | Path,
    output_mp4: str | Path,
) -> dict[str, Any]:
    """Mux silent/story video with narration (replace or add audio)."""
    video_mp4 = Path(video_mp4)
    narration_mp3 = Path(narration_mp3)
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_mp4),
        "-i",
        str(narration_mp3),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    ok = proc.returncode == 0 and output_mp4.is_file() and output_mp4.stat().st_size > 100
    if not ok:
        raise RuntimeError(
            f"ffmpeg mux failed: {(proc.stderr or proc.stdout or '')[-400:]}"
        )
    return {"ok": True, "path": str(output_mp4), "cmd": cmd}
