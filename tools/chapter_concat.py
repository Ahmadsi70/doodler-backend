"""
Concatenate chapter/part MP4s into one ``render.mp4`` (FFmpeg concat demuxer).

Why: long narratives exceed a single Light batch; parts stay inspectable, final is one file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


DEFAULT_BATCH_SHOTS = 12


def chunk_shots(shots: list, *, batch_size: int = DEFAULT_BATCH_SHOTS) -> list[list]:
    """Split shot list into contiguous batches (last batch may be shorter)."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if not shots:
        return []
    return [shots[i : i + batch_size] for i in range(0, len(shots), batch_size)]


def concat_mp4s(
    parts: Sequence[Path | str],
    dest: Path | str,
    *,
    ffmpeg: str,
) -> Path:
    """
    Concat demuxer: write list file next to dest, produce ``dest`` MP4.
    """
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = [Path(p) for p in parts]
    missing = [p for p in paths if not p.is_file() or p.stat().st_size <= 0]
    if missing:
        raise FileNotFoundError(f"concat parts missing/empty: {missing}")
    if len(paths) == 1:
        if paths[0].resolve() != out.resolve():
            out.write_bytes(paths[0].read_bytes())
        return out.resolve()

    list_file = out.parent / "_chapter_concat.txt"
    lines = [f"file '{p.resolve().as_posix()}'" for p in paths]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        # fallback: re-encode if copy fails (codec mismatch)
        cmd_re = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ]
        proc2 = subprocess.run(cmd_re, capture_output=True, text=True)
        if proc2.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
            raise RuntimeError(
                "FFmpeg chapter concat failed:\n"
                + ((proc2.stderr or proc.stderr or "")[-2000:])
            )
    return out.resolve()
