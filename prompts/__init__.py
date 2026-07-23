"""Studio prompt packs loaded from markdown on disk."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_ROOT = Path(__file__).resolve().parent


def prompt_path(studio: str, agent_file: str) -> Path:
    """Return path to ``prompts/<studio>/<agent_file>``."""
    return _PROMPTS_ROOT / studio / agent_file


def load_prompt(studio: str, agent_file: str) -> str:
    """Load a studio agent system prompt from disk."""
    path = prompt_path(studio, agent_file)
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt pack file: {path}")
    return path.read_text(encoding="utf-8")


def list_prompts(studio: str) -> list[str]:
    """List markdown prompt filenames for a studio."""
    folder = _PROMPTS_ROOT / studio
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.glob("*.md"))
