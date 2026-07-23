"""Durable per-job status JSON under the job workspace."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

STATUS_FILENAME = "job_status.json"

VALID = frozenset(
    {"queued", "running", "succeeded", "failed", "cancelled"}
)


def status_path(job_dir: Path | str) -> Path:
    return Path(job_dir) / STATUS_FILENAME


def now_ts() -> float:
    return time.time()


def write_job_status(
    job_dir: Path | str,
    *,
    job_id: str,
    status: str,
    kind: str = "",
    phase: str = "",
    error: str | None = None,
    rq_job_id: str | None = None,
    artifacts: dict[str, Any] | None = None,
    extras: dict[str, Any] | None = None,
    log_line: str | None = None,
    merge: bool = True,
) -> dict[str, Any]:
    if status not in VALID:
        raise ValueError(f"invalid status: {status}")
    path = status_path(job_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if merge and path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
    logs = list(prev.get("logs") or [])
    if log_line:
        logs.append(log_line)
        logs = logs[-200:]
    data = {
        **prev,
        "job_id": job_id,
        "status": status,
        "kind": kind or prev.get("kind") or "",
        "phase": phase or prev.get("phase") or "",
        "error": error,
        "rq_job_id": rq_job_id if rq_job_id is not None else prev.get("rq_job_id"),
        "artifacts": artifacts if artifacts is not None else prev.get("artifacts") or {},
        "extras": extras if extras is not None else prev.get("extras") or {},
        "logs": logs,
        "updated_at": now_ts(),
        "created_at": prev.get("created_at") or now_ts(),
        "job_out_dir": str(Path(job_dir).resolve()),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def read_job_status(job_dir: Path | str) -> dict[str, Any] | None:
    path = status_path(job_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_artifact_files(job_dir: Path | str) -> list[dict[str, Any]]:
    root = Path(job_dir)
    if not root.is_dir():
        return []
    interesting = {
        "render.mp4",
        "scene_ir.json",
        "render_profile.json",
        "style_profile.json",
        "pack_quality_gate.json",
        "job_status.json",
        "story_props.json",
        "story_supervisor.json",
        "williams_timing.json",
        "chapters.json",
    }
    out: list[dict[str, Any]] = []
    for name in sorted(interesting):
        p = root / name
        if p.is_file():
            out.append(
                {
                    "name": name,
                    "path": str(p.resolve()),
                    "size": p.stat().st_size,
                }
            )
    slides = root / "slides"
    if slides.is_dir():
        pngs = sorted(slides.glob("slide_*.png"))
        if pngs:
            out.append(
                {
                    "name": "slides/",
                    "path": str(slides.resolve()),
                    "size": sum(p.stat().st_size for p in pngs),
                    "count": len(pngs),
                }
            )
    return out
