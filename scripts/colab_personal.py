#!/usr/bin/env python3
"""
Personal Colab helper — export-only Story bundle (no in-tool render).

Run from notebook after Story is at ROOT (default /content/Story).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def setup_env(*, out_root: str | None = None) -> Path:
    root = Path(os.environ.get("STORY_ROOT") or "/content/Story").resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Story not found at {root}. Run notebook cell 1 to copy from Drive first."
        )
    sys.path.insert(0, str(root))
    os.chdir(root)
    os.environ.setdefault("STORY_USE_LLM", "0")
    os.environ.setdefault("ANIMATION_DETERMINISTIC_SLIDES", "1")
    os.environ.setdefault("QUALITY_GATE_STRICT", "0")
    if out_root:
        Path(out_root).mkdir(parents=True, exist_ok=True)
        os.environ["ANIMATION_OUT_ROOT"] = out_root
    elif "ANIMATION_OUT_ROOT" not in os.environ:
        d = Path("/content/drive/MyDrive/StoryOut")
        if d.parent.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            os.environ["ANIMATION_OUT_ROOT"] = str(d)
        else:
            os.environ["ANIMATION_OUT_ROOT"] = str(root / "out")
    return root


def probe() -> dict:
    from tools.story_pipeline import readiness_probe

    return readiness_probe()


def export_personal(
    brief: str,
    *,
    seconds: float = 30.0,
    character_path: str | None = None,
    use_llm: bool = False,
    quality: str = "light",
) -> dict:
    """Export screenplay + prompts + engine code; copy bundle to ANIMATION_OUT_ROOT."""
    from tools.job_workspace import job_workspace, new_job_id
    from tools.story_pipeline import run_story_job

    extras = {
        "quality": quality,
        "runtime_seconds": float(seconds),
        "use_llm": bool(use_llm),
        "ai_fill": False,
    }
    if character_path:
        extras["character_path"] = character_path

    def on_event(kind: str, payload) -> None:
        if kind in {"phase", "log"}:
            print(f"[{kind}] {payload}", flush=True)

    job_id = new_job_id()
    result = run_story_job(brief.strip(), job_id, extras, on_event=on_event)
    art = result.get("artifacts") or {}
    export_root = Path(str(art.get("export_root") or ""))
    out_base = Path(os.environ.get("ANIMATION_OUT_ROOT") or job_workspace(job_id))
    if export_root.is_dir():
        dest = out_base / job_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(export_root, dest)
        art["drive_copy"] = str(dest)
        result["artifacts"] = art
    return result


def render_personal(*args, **kwargs) -> dict:
    """Deprecated alias — export only."""
    return export_personal(*args, **kwargs)


def main() -> int:
    root = setup_env()
    print("ROOT=", root)
    print("OUT=", os.environ.get("ANIMATION_OUT_ROOT"))
    p = probe()
    print(json.dumps({k: p.get(k) for k in ("ok", "ffmpeg", "remotion")}, indent=2))
    if not p.get("ok"):
        return 1
    brief = os.environ.get(
        "STORY_BRIEF",
        "Hero enters a quiet hall.\n\n"
        "Then they react in shock because a letter burns.\n\n"
        "They leave into the rain.",
    )
    result = export_personal(brief, seconds=float(os.environ.get("STORY_SECONDS", "24")))
    export_root = (result.get("artifacts") or {}).get("export_root")
    print("export_root=", export_root)
    return 0 if export_root and Path(str(export_root)).is_dir() else 2


if __name__ == "__main__":
    raise SystemExit(main())
