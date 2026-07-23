"""Studio knowledge libraries (JSON rule packs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LIBRARIES_ROOT = Path(__file__).resolve().parent


def library_path(studio: str, name: str) -> Path:
    """Return path to ``libraries/<studio>/<name>``."""
    return _LIBRARIES_ROOT / studio / name


def load_library(studio: str, name: str) -> Any:
    """Load a JSON library file for a studio."""
    path = library_path(studio, name)
    if not path.is_file():
        raise FileNotFoundError(f"Missing library file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_libraries(studio: str) -> list[str]:
    """List JSON library filenames for a studio."""
    folder = _LIBRARIES_ROOT / studio
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.glob("*.json"))
