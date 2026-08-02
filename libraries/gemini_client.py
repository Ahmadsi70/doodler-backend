"""
Gemini Developer API client (REST via httpx).

Why: Storyboard scene planning uses Gemini Flash via REST (no extra SDK);
keys load from ``.env`` (``GOOGLE_API_KEY`` / ``GEMINI_API_KEY``). Retired
model ids (1.5/2.5-flash) auto-fallback to ``gemini-flash-latest``.
Native image models (Nano Banana / Flash Image) generate cinematic stills
without pulling in the Google GenAI SDK.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

import httpx

# Stable alias on Developer API (1.5/2.5-flash often 404 for new keys).
DEFAULT_MODEL = "gemini-flash-latest"
FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-lite-latest",
)
# Image-capable models (try newest first).
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"
IMAGE_FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
)
_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def _api_key(env: Mapping[str, str] | None = None) -> str:
    """Resolve API key; fail closed when absent."""
    src = env if env is not None else os.environ
    key = (src.get("GOOGLE_API_KEY") or src.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) required")
    return key


def gemini_model_id() -> str:
    """Preferred model id from env; default Flash alias."""
    return (os.environ.get("STORY_GEMINI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _model_chain(preferred: str | None = None) -> list[str]:
    """Ordered model ids to try (env first, then known-good fallbacks)."""
    first = (preferred or gemini_model_id()).strip()
    chain: list[str] = []
    for mid in (first, *FALLBACK_MODELS):
        if mid and mid not in chain:
            chain.append(mid)
    return chain


def _generate_once(
    prompt: str,
    *,
    model: str,
    timeout: float,
    max_output_tokens: int = 2048,
    temperature: float = 0.4,
) -> str:
    url = f"{_API_ROOT}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": float(temperature),
            "maxOutputTokens": int(max_output_tokens),
        },
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    parts = (
        ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    )
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 60.0,
    max_output_tokens: int = 2048,
    temperature: float = 0.4,
) -> str:
    """
    Call ``models.generateContent`` with fallback across Flash aliases.

    Retries on 404 (retired model) and 429 (quota) using ``FALLBACK_MODELS``.
    """
    last_err: Exception | None = None
    for mid in _model_chain(model):
        try:
            return _generate_once(
                prompt,
                model=mid,
                timeout=timeout,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        except httpx.HTTPStatusError as exc:
            last_err = exc
            code = exc.response.status_code
            if code in (404, 429, 503):
                continue
            raise
    if last_err is not None:
        raise last_err
    raise RuntimeError("No Gemini model available")


def _extract_json_array(text: str) -> list[Any]:
    """Parse a JSON array from model text (tolerates ``` fences)."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("expected JSON array of scenes")
    return data


def _image_model_chain(preferred: str | None = None) -> list[str]:
    first = (
        preferred
        or os.environ.get("STORY_GEMINI_IMAGE_MODEL")
        or DEFAULT_IMAGE_MODEL
    ).strip()
    chain: list[str] = []
    for mid in (first, *IMAGE_FALLBACK_MODELS):
        if mid and mid not in chain:
            chain.append(mid)
    return chain


def _extract_image_bytes(payload: dict[str, Any]) -> bytes:
    """Pull first inline image from a generateContent response."""
    parts = (
        ((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts")
        or []
    )
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline = part.get("inlineData") or part.get("inline_data") or {}
        data = inline.get("data")
        mime = str(inline.get("mimeType") or inline.get("mime_type") or "")
        if data and ("image" in mime or not mime):
            return base64.b64decode(data)
    raise RuntimeError("Gemini image response contained no inline image bytes")


def _generate_image_once(
    prompt: str,
    *,
    model: str,
    timeout: float,
    reference_images: list[bytes] | None = None,
) -> bytes:
    """
    Text→image; optional reference stills keep character/style continuity.

    Why: storybook pages drift unless Gemini sees a locked character sheet.
    """
    url = f"{_API_ROOT}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for raw in reference_images or []:
        if not raw:
            continue
        parts.append(
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(raw).decode("ascii"),
                }
            }
        )
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "16:9"},
        },
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    return _extract_image_bytes(resp.json())


def _generate_image_openrouter(
    prompt: str,
    *,
    timeout: float = 180.0,
) -> bytes:
    """
    Gemini Flash Image through OpenRouter ``/images``.

    Why: Google AI Studio free-tier often has image quota limit:0; OpenRouter
    keeps the same Gemini image model available for Story stills.
    """
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY required for OpenRouter Gemini images")
    model = (
        os.environ.get("OPENROUTER_IMAGE_MODEL") or "google/gemini-2.5-flash-image"
    ).strip()
    base = (
        os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    ).rstrip("/")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/story-local",
        "X-Title": "Story Cinematic",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": "16:9",
        "n": 1,
    }
    resp = httpx.post(
        f"{base}/images", headers=headers, json=payload, timeout=timeout
    )
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") or []
    b64 = (items[0] or {}).get("b64_json") if items else None
    if not b64:
        # Some routers return URL instead of b64.
        url = (items[0] or {}).get("url") if items else None
        if url:
            img = httpx.get(url, timeout=timeout)
            img.raise_for_status()
            return img.content
        raise RuntimeError(f"OpenRouter images empty: {json.dumps(data)[:300]}")
    return base64.b64decode(b64)


def generate_image(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 120.0,
    out_path: str | Path | None = None,
    reference_images: list[bytes] | None = None,
) -> bytes:
    """
    Text→image via Gemini Flash Image (Google REST, then OpenRouter fallback).

    ``reference_images`` are ignored on OpenRouter fallback (text-only there).
    """
    last_err: Exception | None = None
    for mid in _image_model_chain(model):
        try:
            raw = _generate_image_once(
                prompt,
                model=mid,
                timeout=timeout,
                reference_images=reference_images,
            )
            if out_path is not None:
                path = Path(out_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            return raw
        except httpx.HTTPStatusError as exc:
            last_err = exc
            if exc.response.status_code in (404, 429, 503):
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue

    # Paid/routed Gemini image path when Studio free-tier image quota is 0.
    if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
        try:
            raw = _generate_image_openrouter(prompt, timeout=max(timeout, 180.0))
            if out_path is not None:
                path = Path(out_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            return raw
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    if last_err is not None:
        raise RuntimeError(f"Gemini image generation failed: {last_err}") from last_err
    raise RuntimeError("No Gemini image model available")


def plan_storyboard_scenes(
    topic: str,
    *,
    target_sec: float,
    language: str,
    style_id: str,
    scene_count: int | None = None,
) -> list[dict[str, Any]]:
    """
    Ask Gemini for paced scene cards (narration / visual / duration).

    Why: live Storyboard needs language-aware beat planning; motion stills
    stay local until an image model is wired.
    """
    target = max(8.0, float(target_sec))
    count = scene_count or max(2, min(12, int(round(target / 8.0))))
    prompt = (
        f"You are a storyboard director. Language={language}. Style={style_id}.\n"
        f"Split the story into exactly {count} scenes totaling ~{target:.0f} seconds.\n"
        "Return ONLY a JSON array. Each item keys: narration (string), "
        "visual (English visual prompt), duration_sec (number).\n"
        f"Story:\n{topic.strip()}\n"
    )
    raw = generate_text(prompt)
    rows = _extract_json_array(raw)
    scenes: list[dict[str, Any]] = []
    for i, row in enumerate(rows[:count]):
        if not isinstance(row, dict):
            continue
        scenes.append(
            {
                "index": i,
                "narration": str(row.get("narration") or topic)[:400],
                "visual": str(row.get("visual") or row.get("narration") or topic)[:400],
                "duration_sec": float(row.get("duration_sec") or (target / count)),
                "language": language,
            }
        )
    if len(scenes) < 2:
        raise RuntimeError("Gemini scene plan too short")
    return scenes
