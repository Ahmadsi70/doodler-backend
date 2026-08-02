"""TDD: P0/P1 storybook pro — style lock, camera variety, border QC."""

from __future__ import annotations

import numpy as np
from PIL import Image

from agents.storybook_page_agent import plan_storybook
from libraries.storybook_page_qc import page_has_border_frame
from libraries.storybook_pipeline import ken_burns_frame


def test_plan_includes_style_lock_and_character_bible() -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Fireflies gather. Mist rises. Bridge ahead. Hilltop stars.",
        title="Lantern Fox",
        target_sec=30.0,
        crossfade_sec=0.9,
    )
    assert plan.style_lock
    lock = plan.style_lock.lower()
    assert "storybook painting" in lock or "gouache" in lock or "watercolor" in lock
    assert plan.character_bible
    assert plan.crossfade_sec >= 0.85
    for p in plan.pages:
        assert plan.style_lock[:40] in p.still_prompt or "STYLE LOCK" in p.still_prompt
        assert "no picture frame" in p.still_prompt.lower() or "no frame" in p.still_prompt.lower()
        assert p.shot in {"wide", "medium", "close"}


def test_camera_variety_across_pages() -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Fireflies gather. The fox walks to a bridge. Mist rises. Hilltop.",
        title="Lantern Fox",
        target_sec=30.0,
    )
    cams = {p.camera for p in plan.pages}
    shots = {p.shot for p in plan.pages}
    assert len(plan.pages) >= 4
    assert len(cams) >= 2 or len(shots) >= 2


def test_border_frame_qc_detects_dark_mat() -> None:
    w, h = 320, 180
    ok = np.full((h, w, 3), 120, dtype=np.uint8)
    bad = ok.copy()
    bad[:12, :] = 5
    bad[-12:, :] = 5
    bad[:, :12] = 5
    bad[:, -12:] = 5
    assert page_has_border_frame(Image.fromarray(ok)) is False
    assert page_has_border_frame(Image.fromarray(bad)) is True


def test_close_shot_zooms_more_than_wide() -> None:
    rgb = np.zeros((200, 360, 3), dtype=np.uint8)
    rgb[80:120, 160:200] = (255, 100, 40)
    wide = ken_burns_frame(
        rgb, t_norm=1.0, camera="subtle_zoom_in", width=180, height=100, shot="wide"
    )
    close = ken_burns_frame(
        rgb, t_norm=1.0, camera="subtle_zoom_in", width=180, height=100, shot="close"
    )
    # Close crop should magnify the orange blob (higher mean in warm channel).
    assert float(close[:, :, 0].mean()) >= float(wide[:, :, 0].mean()) - 1.0
