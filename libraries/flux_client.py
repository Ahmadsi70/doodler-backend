"""
FLUX.2 Klein stills via OpenRouter Images API (no local GPU required).

Why: storybook pages need colorful precise painting; Klein is the confirmed
still backend while Gemini remains a fallback.
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

DEFAULT_FLUX_MODEL = "black-forest-labs/flux.2-klein-4b"


def _openrouter_key() -> str:
    return (os.environ.get("OPENROUTER_API_KEY") or "").strip()


def _base_url() -> str:
    return (
        os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    ).rstrip("/")


def _model_id(model: str | None = None) -> str:
    return (
        model
        or os.environ.get("FLUX_IMAGE_MODEL")
        or os.environ.get("OPENROUTER_FLUX_MODEL")
        or DEFAULT_FLUX_MODEL
    ).strip()


def _extract_image_bytes(data: dict[str, Any], *, timeout: float) -> bytes:
    items = data.get("data") or []
    if not items:
        raise RuntimeError(f"OpenRouter Flux images empty: {json.dumps(data)[:300]}")
    first = items[0] or {}
    b64 = first.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = first.get("url")
    if url:
        img = httpx.get(url, timeout=timeout)
        img.raise_for_status()
        return img.content
    raise RuntimeError(f"OpenRouter Flux images empty: {json.dumps(data)[:300]}")


def _post_images(payload: dict[str, Any], *, timeout: float) -> bytes:
    key = _openrouter_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY required for FLUX.2 Klein stills")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/story-local",
        "X-Title": "Story Storybook Flux",
    }
    resp = httpx.post(
        f"{_base_url()}/images",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return _extract_image_bytes(resp.json(), timeout=timeout)


def _shrink_ref_png(raw: bytes, *, max_side: int = 512) -> bytes:
    """Downscale a reference so OpenRouter accepts the data-URL payload."""
    im = Image.open(io.BytesIO(bytes(raw))).convert("RGB")
    im.thumbnail((int(max_side), int(max_side)))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_image(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 180.0,
    out_path: str | Path | None = None,
    aspect_ratio: str = "16:9",
    reference_images: list[bytes] | None = None,
) -> bytes:
    """
    Text→image with FLUX.2 Klein through OpenRouter ``/images``.

    Why refs: character-sheet continuity. Default sends one downscaled sheet
    only; ``FLUX_USE_REFS=1`` allows up to four. On 400, retry text-only.
    """
    payload: dict[str, Any] = {
        "model": _model_id(model),
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "n": 1,
    }
    use_all_refs = (os.environ.get("FLUX_USE_REFS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if reference_images:
        raw_refs = list(reference_images[:4] if use_all_refs else reference_images[:1])
        refs = [
            "data:image/png;base64,"
            + base64.b64encode(_shrink_ref_png(raw)).decode("ascii")
            for raw in raw_refs
        ]
        payload["input_references"] = refs
        try:
            out = _post_images(payload, timeout=timeout)
        except httpx.HTTPStatusError:
            payload.pop("input_references", None)
            out = _post_images(payload, timeout=timeout)
    else:
        out = _post_images(payload, timeout=timeout)

    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(out)
    return out
