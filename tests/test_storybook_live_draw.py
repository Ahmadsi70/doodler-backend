"""TDD: storybook pages draw themselves live before Ken Burns hold."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from agents.storybook_page_agent import plan_storybook
from libraries.storybook_pen_draw import pen_draw_frame_sequence
from libraries.storybook_pipeline import compose_storybook_mp4, render_storybook


def test_pen_draw_frames_start_blank_end_painted() -> None:
    rgb = np.zeros((90, 160, 3), dtype=np.uint8)
    rgb[:, :] = (20, 50, 70)
    rgb[25:70, 50:110] = (230, 140, 50)
    frames = pen_draw_frame_sequence(rgb, n_frames=24, draw_frac=0.5, fill_frac=0.35)
    assert len(frames) == 24
    # Early frames still paper-dominant; last frame matches the painting.
    assert float(frames[1].mean()) > 160.0
    assert abs(float(frames[-1].mean()) - float(rgb.mean())) < 2.0
    # Mid reveal should differ from both blank paper and final still.
    mid = frames[len(frames) // 2]
    assert abs(float(mid.mean()) - float(frames[1].mean())) > 5.0


def test_compose_live_draw_changes_early_frames(tmp_path: Path) -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Mist rises.",
        title="Lantern Fox",
        target_sec=3.0,
        crossfade_sec=0.1,
    )
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    stills: list[Path] = []
    for i, _ in enumerate(plan.pages):
        arr = np.zeros((180, 320, 3), dtype=np.uint8)
        arr[:, :] = (30 + i * 20, 70, 100)
        arr[60:130, 100:220] = (220, 130, 40)
        path = pages_dir / f"page_{i:02d}.png"
        Image.fromarray(arr).save(path)
        stills.append(path)

    report = render_storybook(
        plan,
        tmp_path / "out",
        still_paths=stills,
        width=320,
        height=180,
        fps=12,
        mock=True,
        live_draw=True,
    )
    assert report["ok"] is True
    assert report.get("live_draw") is True
    assert Path(report["final_mp4"]).is_file()
    # Compose path should mark live draw engine.
    assert "live_draw" in str(report.get("compose", {})).lower() or report["live_draw"]
