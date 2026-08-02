"""TDD: product lanes A→B→C stay ordered and non-interfering."""

from __future__ import annotations

import ast
from pathlib import Path

from libraries.product_layers import (
    LANE_A_STORYBOOK,
    LANE_B_EDU,
    LANE_C_CARTOON,
    PRODUCT_NORTH_STAR,
    lane_for_script,
    lane_may_import,
)


ROOT = Path(__file__).resolve().parents[1]


def _imports_of(rel: str) -> set[str]:
    path = ROOT / rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
            if node.module.startswith("libraries.") or node.module.startswith("agents."):
                found.add(node.module)
    return found


def test_north_star_names_three_lanes_in_order() -> None:
    assert PRODUCT_NORTH_STAR == (LANE_A_STORYBOOK, LANE_B_EDU, LANE_C_CARTOON)
    assert LANE_A_STORYBOOK.order == 1
    assert LANE_B_EDU.order == 2
    assert LANE_C_CARTOON.order == 3


def test_script_entrypoints_map_to_lanes() -> None:
    assert lane_for_script("scripts/produce_storybook.py") == "A"
    assert lane_for_script("scripts/produce_scene_pack.py") == "A"
    assert lane_for_script("scripts/produce_edu_lesson.py") == "B"
    assert lane_for_script("scripts/produce_cartoon_studio.py") == "C"


def test_lane_a_core_must_not_depend_on_b_or_c() -> None:
    """Storybook film stays independent; edu/cartoon never leak into core compose."""
    imports = _imports_of("libraries/storybook_pipeline.py")
    assert "libraries.edu_narration" not in imports
    assert "animatediff" not in imports
    assert lane_may_import("A", "libraries.edu_narration") is False
    assert lane_may_import("A", "animatediff") is False


def test_lane_b_may_use_a_but_not_c() -> None:
    imports = _imports_of("libraries/edu_narration.py")
    assert "animatediff" not in imports
    assert lane_may_import("B", "libraries.storybook_pipeline") is True
    assert lane_may_import("B", "animatediff") is False


def test_lane_c_is_isolated_future_surface() -> None:
    assert lane_may_import("C", "libraries.storybook_pipeline") is True  # may reuse stills
    assert lane_may_import("C", "animatediff") is True
    # Cartoon must not own edu narration contract.
    assert "edu_narration" not in LANE_C_CARTOON.owns
