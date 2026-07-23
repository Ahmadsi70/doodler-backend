"""
Bridge to williams-animation-rules (TS) for 24fps timing enrichment.

Runs a small Node script under remotion/ that imports the local file: package.
Non-fatal: returns input timing unchanged when Node/Williams unavailable.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "remotion" / "scripts" / "enrich_timing.mjs"


def enrich_timing_with_williams(
    timing: dict[str, Any],
    *,
    job_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Enrich ``duration_frames`` using Williams UNIVERSAL_FPS helpers."""
    if not _SCRIPT.is_file():
        return dict(timing)
    node = __import__("shutil").which("node")
    if not node:
        return dict(timing)
    payload = json.dumps(timing, ensure_ascii=False)
    try:
        proc = subprocess.run(
            [node, str(_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(_ROOT / "remotion"),
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return dict(timing)
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return dict(timing)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return dict(timing)
    if not isinstance(data, dict):
        return dict(timing)
    data["williams_enriched"] = True
    if job_dir:
        out = Path(job_dir) / "williams_timing.json"
        out.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return data
