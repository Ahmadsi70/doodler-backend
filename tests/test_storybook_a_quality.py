"""TDD: Lane A quality — light-mat QC, live-draw hard cut, Flux sheet refs."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from libraries.storybook_contract import StorybookPage, StorybookPlan
from libraries.storybook_page_qc import (
    page_fails_fullbleed_qc,
    page_has_border_frame,
    page_has_light_mat,
)
from libraries.storybook_pipeline import compose_storybook_mp4


def test_light_mat_qc_detects_beige_frame() -> None:
    w, h = 320, 180
    ok = np.full((h, w, 3), 140, dtype=np.uint8)
    bad = np.full((h, w, 3), 90, dtype=np.uint8)
    # Bright beige mat around darker painting.
    bad[:14, :] = (235, 220, 190)
    bad[-14:, :] = (235, 220, 190)
    bad[:, :14] = (235, 220, 190)
    bad[:, -14:] = (235, 220, 190)
    assert page_has_light_mat(Image.fromarray(ok)) is False
    assert page_has_light_mat(Image.fromarray(bad)) is True
    assert page_fails_fullbleed_qc(Image.fromarray(bad)) is True
    assert page_fails_fullbleed_qc(Image.fromarray(ok)) is False
    assert page_has_border_frame(Image.fromarray(ok)) is False


def test_live_draw_compose_skips_paper_crossfade(tmp_path: Path) -> None:
    """Page boundaries must not dissolve into cream paper (hard cut)."""
    plan = StorybookPlan(
        title="Cut",
        topic="two pages",
        language="en",
        target_sec=4.0,
        crossfade_sec=0.9,
        pages=[
            StorybookPage(
                index=0,
                visual_action="red page",
                hold_sec=2.0,
                camera="static",
                shot="wide",
                mood="warm",
                concept="a",
                emotion="joy",
                camera_angle="eye_level",
                staging="center",
                visual_hook="red",
                still_prompt="STYLE LOCK watercolor red field scene for kids",
            ),
            StorybookPage(
                index=1,
                visual_action="blue page",
                hold_sec=2.0,
                camera="static",
                shot="wide",
                mood="calm",
                concept="b",
                emotion="calm",
                camera_angle="eye_level",
                staging="center",
                visual_hook="blue",
                still_prompt="STYLE LOCK watercolor blue field scene for kids",
            ),
        ],
        style_lock="STYLE LOCK watercolor",
        character_bible="one hero character locked",
        character_sheet_prompt="character sheet one hero watercolor",
    )
    pages = [
        np.full((72, 128, 3), (200, 40, 40), dtype=np.uint8),
        np.full((72, 128, 3), (40, 80, 200), dtype=np.uint8),
    ]
    out = tmp_path / "cut.mp4"
    report = compose_storybook_mp4(
        pages,
        plan,
        out,
        width=128,
        height=72,
        fps=8,
        live_draw=True,
    )
    assert report["live_draw"] is True
    # Hard cut: no crossfade frames stolen → full page frame budget.
    assert report["n_frames"] == 32  # 2s+2s at 8fps


def test_flux_sends_shrunk_sheet_ref_by_default(monkeypatch) -> None:
    from libraries import flux_client

    # Build a larger-than-tiny PNG so shrink path is exercised.
    im = Image.new("RGB", (800, 450), (30, 140, 220))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    sheet = buf.getvalue()

    tiny = Image.new("RGB", (16, 9), (255, 0, 0))
    tbuf = io.BytesIO()
    tiny.save(tbuf, format="PNG")
    out_png = tbuf.getvalue()
    b64 = base64.b64encode(out_png).decode("ascii")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("FLUX_USE_REFS", raising=False)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"b64_json": b64}]}

    with patch("libraries.flux_client.httpx.post", return_value=mock_resp) as post:
        flux_client.generate_image("fox", reference_images=[sheet, sheet])
    payload = post.call_args.kwargs.get("json") or post.call_args[1].get("json")
    refs = payload.get("input_references") or []
    assert len(refs) == 1  # sheet-only by default (not prev_page flood)
    assert refs[0].startswith("data:image/png;base64,")
    # Shrunk payload should be smaller than original sheet bytes as base64.
    ref_b64 = refs[0].split(",", 1)[1]
    assert len(ref_b64) < len(base64.b64encode(sheet).decode("ascii"))
