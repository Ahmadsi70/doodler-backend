"""TDD: FLUX.2 Klein still backend via OpenRouter Images API."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from libraries.storybook_pipeline import resolve_page_still


def _tiny_png_bytes() -> bytes:
    buf = BytesIO()
    Image.fromarray(np.full((32, 48, 3), (200, 80, 40), dtype=np.uint8)).save(
        buf, format="PNG"
    )
    return buf.getvalue()


def test_flux_generate_image_decodes_openrouter_b64(monkeypatch) -> None:
    from libraries import flux_client

    png = _tiny_png_bytes()
    b64 = base64.b64encode(png).decode("ascii")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("FLUX_API_URL", raising=False)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"b64_json": b64}]}

    with patch("libraries.flux_client.httpx.post", return_value=mock_resp) as post:
        out = flux_client.generate_image(
            "colorful storybook fox with blue lantern",
            aspect_ratio="16:9",
        )
    assert out == png
    payload = post.call_args.kwargs.get("json") or post.call_args[1].get("json")
    assert payload["model"] == "black-forest-labs/flux.2-klein-4b"
    assert "fox" in payload["prompt"].lower()
    assert payload["aspect_ratio"] == "16:9"


def test_resolve_page_still_uses_flux_backend(monkeypatch, tmp_path: Path) -> None:
    png = _tiny_png_bytes()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("STILL_BACKEND", "flux")

    with patch(
        "libraries.flux_client.generate_image", return_value=png
    ) as gen:
        im, tag = resolve_page_still(
            "painted storybook page",
            width=96,
            height=54,
            index=0,
            mock=False,
            still_backend="flux",
        )
    assert tag == "flux"
    assert gen.called
    assert im.size == (96, 54)
    assert im.mode == "RGB"
    _ = tmp_path


def test_flux_sends_one_shrunk_ref_by_default(monkeypatch) -> None:
    from libraries import flux_client

    png = _tiny_png_bytes()
    b64 = base64.b64encode(png).decode("ascii")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("FLUX_USE_REFS", raising=False)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"b64_json": b64}]}

    with patch("libraries.flux_client.httpx.post", return_value=mock_resp) as post:
        flux_client.generate_image("fox", reference_images=[png, png])
    payload = post.call_args.kwargs.get("json") or post.call_args[1].get("json")
    refs = payload.get("input_references") or []
    assert len(refs) == 1


def test_resolve_page_still_flux_falls_back_to_gemini(monkeypatch) -> None:
    png = _tiny_png_bytes()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")

    with (
        patch(
            "libraries.flux_client.generate_image",
            side_effect=RuntimeError("flux down"),
        ),
        patch(
            "libraries.gemini_client.generate_image", return_value=png
        ) as gem,
    ):
        im, tag = resolve_page_still(
            "painted page",
            width=64,
            height=36,
            index=1,
            mock=False,
            still_backend="flux",
        )
    assert tag == "gemini_fallback"
    assert gem.called
    assert im.size == (64, 36)
