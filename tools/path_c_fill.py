"""Path C AI fill is not part of Story (character photo via CLI/UI only)."""

from __future__ import annotations

from typing import Any


def run_path_c_fill(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "Path C AI fill is not part of Story. Provide --character / character_main."
    )
