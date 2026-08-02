"""Guard: cutout / cinematic stacks must stay removed."""

from __future__ import annotations

import importlib
import pytest

_GONE = [
    "libraries.narrative_visual_pipeline",
    "libraries.cinematic_compositor",
    "libraries.layer_pack",
    "libraries.cinematic_cutout_pipeline",
    "libraries.style_orchestrator",
    "agents.visual_cast_agent",
    "agents.video_script_agent",
    "agents.narrative_director_agent",
]


@pytest.mark.parametrize("mod", _GONE)
def test_legacy_modules_removed(mod: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)
