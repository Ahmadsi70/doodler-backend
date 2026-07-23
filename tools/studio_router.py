"""StudioRouter — Story pack only."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from tools.studio_profiles import STORY_STUDIO, normalize_kind
except ImportError:
    from .studio_profiles import STORY_STUDIO, normalize_kind

try:
    from prompts import list_prompts, load_prompt
    from libraries import list_libraries, load_library
except ImportError:
    from ..prompts import list_prompts, load_prompt
    from ..libraries import list_libraries, load_library

STORY_PACK = "story"

ROLE_TO_PROMPT: dict[str, dict[str, str]] = {
    "narrative": {STORY_PACK: "storyboard_agent.md"},
    "nlp": {STORY_PACK: "storyboard_agent.md"},
    "semiotics": {STORY_PACK: "cinematography_agent.md"},
    "cinematography": {STORY_PACK: "cinematography_agent.md"},
    "timing": {STORY_PACK: "animation_timing_agent.md"},
    "continuity": {STORY_PACK: "continuity_agent.md"},
    "quality_gate": {STORY_PACK: "quality_gate_agent.md"},
    "supervisor": {STORY_PACK: "story_supervisor_agent.md"},
    "manager": {STORY_PACK: "story_supervisor_agent.md"},
    "auditor": {STORY_PACK: "story_supervisor_agent.md"},
}

PACK_NAMES = frozenset({STORY_PACK})


def pack_for_studio(studio: str | None = None) -> str:
    return STORY_PACK


def prompt_file_for_role(role: str, *, studio: str | None = None) -> str | None:
    return (ROLE_TO_PROMPT.get(role) or {}).get(STORY_PACK)


@lru_cache(maxsize=64)
def _cached_prompt(pack: str, filename: str) -> str:
    return load_prompt(pack, filename)


def load_agent_system_prompt(
    role: str, *, studio: str | None = None
) -> str | None:
    filename = prompt_file_for_role(role, studio=studio)
    if not filename:
        return None
    try:
        return _cached_prompt(STORY_PACK, filename)
    except FileNotFoundError:
        return None


def compose_system_prompt(
    role: str,
    invocation: str,
    *,
    studio: str | None = None,
    fallback: str,
) -> str:
    packed = load_agent_system_prompt(role, studio=studio)
    header = f"[StudioPack:{STORY_PACK} role={role}]\n"
    if not packed:
        return f"{header}{fallback}\n\n## Invocation constraints\n{invocation}"
    return (
        f"{header}{packed.strip()}\n\n"
        f"## Invocation constraints\n{invocation.strip()}"
    )


def load_quality_context(*, studio: str | None = None, limit: int = 8) -> str:
    parts = [f"studio_pack={STORY_PACK}"]
    try:
        checklist = load_library(STORY_PACK, "quality_checklist.json")
        items = checklist if isinstance(checklist, list) else checklist.get("checks", [])
        bits = []
        for item in items[:limit]:
            if isinstance(item, str):
                bits.append(item)
            elif isinstance(item, dict):
                bits.append(str(item.get("criteria") or item.get("check_id") or item))
        if bits:
            parts.append("checklist_top=" + " | ".join(bits))
    except FileNotFoundError:
        pass
    return "\n".join(parts)


def pack_inventory(*, studio: str | None = None) -> dict[str, Any]:
    return {
        "studio_kind": STORY_STUDIO,
        "pack": STORY_PACK,
        "prompts": list_prompts(STORY_PACK),
        "libraries": list_libraries(STORY_PACK),
    }


def clear_prompt_cache() -> None:
    _cached_prompt.cache_clear()
