"""
Story git hygiene — recommend / verify dedicated repo root.

Why: nesting Story under the user-home git repo breaks CI and ownership.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_REQUIRED_GITIGNORE = (
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    "out/",
    ".env",
    "*.mp4",
    "node_modules/",
    "remotion/node_modules/",
    "remotion/public/story_props.json",
    "remotion/public/character.png",
    "remotion/public/audio/",
    "remotion/public/layers/",
    "_audio_src/",
    ".streamlit/secrets.toml",
)


def story_root_gitignore_entries() -> tuple[str, ...]:
    return _REQUIRED_GITIGNORE


def recommend_story_git_init(root: Path | str) -> dict[str, Any]:
    """Report whether Story has its own .git and required gitignore lines."""
    r = Path(root).resolve()
    git_dir = r / ".git"
    gi = r / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    missing = [e for e in _REQUIRED_GITIGNORE if e not in text]
    return {
        "root": str(r),
        "has_git": git_dir.is_dir(),
        "gitignore_ok": len(missing) == 0,
        "missing_gitignore": missing,
        "advice": (
            "ok"
            if git_dir.is_dir() and not missing
            else "run: git init in Story + refresh .gitignore"
        ),
    }
