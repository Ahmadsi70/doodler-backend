"""TDD: cartoon still → progressive pen-draw reveal MP4."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from libraries.storybook_pen_draw import render_pen_draw_mp4


def test_pen_draw_writes_mp4(tmp_path: Path) -> None:
    arr = np.zeros((120, 200, 3), dtype=np.uint8)
    arr[:, :] = (30, 60, 90)
    # Simple fox-ish blob + contrast edges
    arr[40:90, 70:140] = (220, 140, 60)
    arr[50:70, 100:120] = (40, 40, 40)
    still = tmp_path / "page.png"
    Image.fromarray(arr).save(still)
    out = tmp_path / "pen.mp4"
    report = render_pen_draw_mp4(
        still,
        out,
        duration_sec=1.0,
        fps=12,
        width=200,
        height=120,
    )
    assert report["ok"] is True
    assert out.is_file()
    assert out.stat().st_size > 500
    assert report["n_frames"] >= 12
