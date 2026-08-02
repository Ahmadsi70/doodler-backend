"""TDD: faster live-draw ordered by scenario beat details."""

from __future__ import annotations

import numpy as np

from libraries.storybook_pen_draw import (
    pen_draw_frame_sequence,
    scenario_focus_terms,
)
from libraries.storybook_pipeline import _page_frame_sequence


def test_scenario_focus_terms_from_beat() -> None:
    terms = scenario_focus_terms(
        "The fox carries the blue lantern across the bridge while fireflies gather"
    )
    assert terms[0] == "hero"
    assert "lantern" in terms
    assert "fireflies" in terms
    assert "bridge" in terms


def test_hero_region_appears_before_background_fill() -> None:
    h, w = 120, 200
    rgb = np.full((h, w, 3), 240, dtype=np.uint8)  # paper-like bg
    # Left: cool teal background block
    rgb[:, :80] = (30, 90, 80)
    # Center-right: orange fox blob
    rgb[40:90, 110:170] = (230, 120, 40)
    # Cyan lantern speck
    rgb[50:70, 175:190] = (40, 200, 230)

    frames = pen_draw_frame_sequence(
        rgb,
        n_frames=30,
        visual_action="orange fox finds glowing blue lantern",
        draw_frac=0.55,
        fill_frac=0.35,
    )
    mid = frames[10]
    # At mid-draw, fox region should be more revealed than far-left forest.
    fox = float(mid[40:90, 110:170].mean())
    left = float(mid[:, :40].mean())
    # Fox patch darker/more saturated away from paper than empty left paper remnant,
    # OR fox already painted while left still near paper white.
    assert fox < 220.0 or left > fox


def test_page_sequence_draw_budget_is_fast() -> None:
    rgb = np.zeros((90, 160, 3), dtype=np.uint8)
    rgb[:, :] = (40, 80, 70)
    rgb[30:60, 60:100] = (220, 130, 50)
    frames = _page_frame_sequence(
        rgb,
        hold_sec=8.0,
        camera="subtle_zoom_in",
        shot="wide",
        fps=12,
        width=160,
        height=90,
        live_draw=True,
        visual_action="fox with lantern",
    )
    # 8s * 12fps = 96 frames; draw budget ~2.5s → ~30 draw frames, rest settle.
    assert len(frames) == 96
    # Late frames should be fully painted (near source mean), not stuck on paper.
    assert float(frames[-1].mean()) < 120.0
