"""
Per-job workspace isolation — Cloud Hardening.

Every generation request owns `python/out/<job_id>/` so multi-tenant
Streamlit / cloud workers never clobber shared artifacts.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Iterable, Sequence


def new_job_id() -> str:
    return str(uuid.uuid4())


def default_jobs_root() -> Path:
    """Job artifact root.

    Prefer ``ANIMATION_OUT_ROOT`` (Colab: Drive path) so workers write
    directly to persistent storage — no symlink into Google Drive FUSE.
    """
    override = (os.environ.get("ANIMATION_OUT_ROOT") or "").strip()
    if override:
        root = Path(override).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()
    return Path(__file__).resolve().parent.parent / "out"


def job_workspace(job_id: str, *, root: Path | str | None = None) -> Path:
    if not job_id or not str(job_id).strip():
        raise ValueError("job_id is required for tenant isolation")
    # Prevent path traversal
    safe = Path(str(job_id).strip()).name
    if safe != str(job_id).strip() or ".." in safe:
        raise ValueError(f"invalid job_id: {job_id!r}")
    base = Path(root) if root else default_jobs_root()
    path = (base / safe).resolve()
    if base.resolve() not in path.parents and path != base.resolve():
        # path must be direct child of base
        if path.parent != base.resolve():
            raise ValueError(f"job workspace escaped root: {path}")
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(exist_ok=True)
    (path / "storyboard").mkdir(exist_ok=True)
    (path / "synthetic").mkdir(exist_ok=True)
    return path


def expected_artifacts(
    job_dir: Path | str,
    *,
    storyboard: bool = False,
    render: bool = False,
    props: bool = False,
    synthetic: bool = False,
    synthetic_count: int = 1,
) -> list[Path]:
    """Declare which files the UI / emitter must wait for (Story 2D)."""
    root = Path(job_dir)
    paths: list[Path] = [root / "scene_ir.json"]
    if storyboard:
        paths.append(root / "storyboard")
    if render:
        paths.append(root / "render.mp4")
    if props:
        paths.append(root / "story_props.json")
    if synthetic:
        paths.append(root / "synthetic" / "sdg_manifest.json")
    return paths


def wait_for_artifacts(
    paths: Sequence[Path | str],
    *,
    timeout_sec: float = 600.0,
    poll_interval_sec: float = 1.0,
    min_bytes: int = 1,
    require_storyboard_pngs: bool = False,
) -> dict[str, object]:
    """
    Block until every path exists (dirs may need child PNGs) or timeout.

    Returns {"ok": bool, "ready": [...], "missing": [...], "elapsed_sec": float}.
    """
    targets = [Path(p) for p in paths]
    start = time.monotonic()
    ready: list[str] = []
    missing: list[str] = []

    def _satisfied(path: Path) -> bool:
        if path.is_dir():
            if require_storyboard_pngs or path.name == "storyboard":
                pngs = list(path.glob("storyboard_f*.png")) + list(path.glob("*.png"))
                return any(p.is_file() and p.stat().st_size >= min_bytes for p in pngs)
            if path.name == "synthetic":
                return (path / "sdg_manifest.json").is_file()
            return True
        if not path.is_file():
            return False
        return path.stat().st_size >= min_bytes

    while True:
        ready = []
        missing = []
        for path in targets:
            if _satisfied(path):
                ready.append(str(path))
            else:
                missing.append(str(path))
        if not missing:
            return {
                "ok": True,
                "ready": ready,
                "missing": [],
                "elapsed_sec": time.monotonic() - start,
            }
        if time.monotonic() - start >= timeout_sec:
            return {
                "ok": False,
                "ready": ready,
                "missing": missing,
                "elapsed_sec": time.monotonic() - start,
            }
        time.sleep(max(0.1, poll_interval_sec))


def list_storyboard_pngs(job_dir: Path | str) -> list[Path]:
    d = Path(job_dir) / "storyboard"
    if not d.is_dir():
        return []
    return sorted(d.glob("storyboard_f*.png"))


def list_synthetic_pngs(job_dir: Path | str) -> list[Path]:
    d = Path(job_dir) / "synthetic"
    if not d.is_dir():
        return []
    return sorted(d.glob("sdg_*.png"))
