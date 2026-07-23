"""
Export bundle gate — verify construction pack is complete before user leaves Story.

Why: fail-closed QA so external render uses an approved, complete instruction set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REQUIRED_ALWAYS = (
    "studio_spec.json",
    "screenplay.md",
    "screenplay.json",
    "explanation.md",
    "manifest.json",
    "README.md",
)


def run_export_bundle_gate(root: Path | str, *, targets: list[str] | None = None) -> dict[str, Any]:
    """Check required files exist under export root."""
    base = Path(root)
    missing: list[str] = []
    for name in _REQUIRED_ALWAYS:
        if not (base / name).is_file():
            missing.append(name)
    chosen = targets or ["prompts", "remotion", "slideshow"]
    if "prompts" in chosen:
        if not (base / "prompts" / "film.txt").is_file():
            missing.append("prompts/film.txt")
        if not (base / "prompts" / "guide.md").is_file():
            missing.append("prompts/guide.md")
        if not (base / "prompts" / "film_motion.txt").is_file():
            missing.append("prompts/film_motion.txt")
        if not (base / "prompts" / "motion_guide.md").is_file():
            missing.append("prompts/motion_guide.md")
        motion_sample = base / "prompts" / "shot_00_motion.txt"
        if not motion_sample.is_file():
            # allow empty shot list edge case
            has_shots = (base / "screenplay.json").is_file()
            if has_shots:
                missing.append("prompts/shot_00_motion.txt")
    if "remotion" in chosen:
        for rel in ("engines/remotion/story_props.json", "engines/remotion/guide.md"):
            if not (base / rel).is_file():
                missing.append(rel)
    if "slideshow" in chosen:
        for rel in ("engines/slideshow/build.py", "engines/slideshow/guide.md"):
            if not (base / rel).is_file():
                missing.append(rel)
    ok = len(missing) == 0
    return {
        "ok": ok,
        "missing": missing,
        "checked": str(base.resolve()),
        "targets": chosen,
    }


def write_export_gate(root: Path | str, gate: dict[str, Any]) -> Path:
    path = Path(root) / "export_gate.json"
    path.write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
