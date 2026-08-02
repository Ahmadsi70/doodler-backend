"""
Product lanes A → B → C (ordered, non-interfering).

Why: one north star with three maturity stages. Later cartoon work must not
rewrite the storybook film core or the edu narration layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductLane:
    """One shippable product surface with explicit ownership boundaries."""

    id: str
    order: int
    name: str
    promise: str
    entrypoints: tuple[str, ...]
    owns: tuple[str, ...]
    # Modules this lane must never import (hard isolation).
    forbidden_imports: tuple[str, ...]


LANE_A_STORYBOOK = ProductLane(
    id="A",
    order=1,
    name="Kids Storybook Film",
    promise=(
        "Short watercolor page-film: directed stills + live color pen + Ken Burns "
        "(silent or light score). Character continuity locked."
    ),
    entrypoints=(
        "scripts/produce_storybook.py",
        "scripts/produce_scene_pack.py",
    ),
    owns=(
        "libraries.storybook_pipeline",
        "libraries.storybook_pen_draw",
        "libraries.storybook_visual_directing",
        "libraries.storybook_scene_pack",
        "libraries.flux_client",
    ),
    forbidden_imports=("libraries.edu_narration", "animatediff"),
)

LANE_B_EDU = ProductLane(
    id="B",
    order=2,
    name="Kids Edu Micro-Lessons",
    promise=(
        "Lane A visuals + short English narration on one concept. "
        "Not a dry lecture video."
    ),
    entrypoints=("scripts/produce_edu_lesson.py",),
    owns=("libraries.edu_narration",),
    forbidden_imports=("animatediff",),
)

LANE_C_CARTOON = ProductLane(
    id="C",
    order=3,
    name="Full Cartoon Studio",
    promise=(
        "Future: lip-sync / character motion / AnimateDiff on a separate track. "
        "May consume Lane A stills; must not replace A compose or B narration."
    ),
    entrypoints=("scripts/produce_cartoon_studio.py",),
    owns=("animatediff",),
    # Cartoon owns motion — not the edu cue contract.
    forbidden_imports=("libraries.edu_narration",),
)

PRODUCT_NORTH_STAR: tuple[ProductLane, ...] = (
    LANE_A_STORYBOOK,
    LANE_B_EDU,
    LANE_C_CARTOON,
)

_LANES = {lane.id: lane for lane in PRODUCT_NORTH_STAR}


def lane_for_script(script_path: str | Path) -> str | None:
    """Return lane id for a produce script path, if mapped."""
    norm = Path(script_path).as_posix().replace("\\", "/")
    if not norm.startswith("scripts/"):
        parts = Path(norm).parts
        if "scripts" in parts:
            i = parts.index("scripts")
            norm = "/".join(parts[i:])
        else:
            norm = f"scripts/{Path(norm).name}"
    for lane in PRODUCT_NORTH_STAR:
        if norm in lane.entrypoints:
            return lane.id
    return None


def lane_may_import(lane_id: str, module: str) -> bool:
    """
    Import policy across lanes.

    A: storybook only (no edu, no animatediff)
    B: may use A modules; never animatediff
    C: may reuse A stills/pipeline helpers; may use animatediff; not edu_narration
    """
    lane = _LANES[lane_id]
    mod = module.strip()
    for forbidden in lane.forbidden_imports:
        if mod == forbidden or mod.startswith(forbidden + "."):
            return False
    if lane_id == "A":
        return not (
            mod.startswith("libraries.edu_")
            or mod == "animatediff"
            or mod.startswith("animatediff.")
        )
    if lane_id in ("B", "C"):
        return True
    return False
