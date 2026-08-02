"""TDD: live colorful pen tip paints the still (not black ink / white mask)."""

from __future__ import annotations

import numpy as np

from libraries.storybook_pen_draw import pen_draw_frame_sequence


def test_color_pen_paints_source_hues_midway() -> None:
    h, w = 120, 200
    rgb = np.full((h, w, 3), 245, dtype=np.uint8)
    # Saturated orange subject
    rgb[35:90, 70:150] = (230, 90, 40)
    frames = pen_draw_frame_sequence(
        rgb,
        n_frames=36,
        draw_frac=0.55,
        fill_frac=0.35,
        visual_action="boy builds colorful balloons",
        color_strokes=True,
    )
    mid = frames[16]
    # Midway should already show orange paint, not only cream paper.
    patch = mid[40:85, 80:140]
    assert float(patch[:, :, 0].mean()) > 140.0
    assert float(patch[:, :, 2].mean()) < float(patch[:, :, 0].mean()) - 20.0
    # Final equals source
    assert abs(float(frames[-1].mean()) - float(rgb.mean())) < 2.0
