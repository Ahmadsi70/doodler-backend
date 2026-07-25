from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

ANALYSIS_SYSTEM_PROMPT = """You are a character design analyst. Given a character image, provide a detailed structured analysis covering:

1. Physical appearance (gender, age, body type, height)
2. Facial features (face shape, eyes, nose, mouth, expression)
3. Hairstyle (color, length, style)
4. Clothing (type, colors, patterns, accessories)
5. Dominant colors (list main hex colors with labels)
6. Art style (realistic, cartoon, anime, painterly, etc.)
7. Pose description
8. Style tags (comma-separated keywords for consistent rendering)

Respond with a single JSON object only."""


def _encode_image(image_path: str | Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_character_image(
    image_path: str | Path,
    model: str = "gpt-4o",
) -> dict[str, Any] | None:
    if not Path(image_path).is_file():
        return None

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip() or None
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip() or "https://api.openai.com/v1"

    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)

    b64 = _encode_image(image_path)
    data_url = f"data:image/{Path(image_path).suffix.lstrip('.').replace('jpg', 'jpeg')};base64,{b64}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this character image in detail."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            return None
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def describe_character(analysis: dict[str, Any] | None) -> str:
    if not analysis:
        return ""

    parts = []
    if analysis.get("physical_description"):
        parts.append(analysis["physical_description"])
    if analysis.get("clothing"):
        colors = analysis.get("clothing_colors", [])
        color_str = f" با رنگ‌های {', '.join(colors[:3])}" if colors else ""
        parts.append(f"لباس: {analysis['clothing']}{color_str}")
    if analysis.get("hairstyle"):
        parts.append(f"مو: {analysis['hairstyle']}")
    if analysis.get("facial_features"):
        parts.append(f"صورت: {analysis['facial_features']}")
    if analysis.get("pose_description"):
        parts.append(f"حالت: {analysis['pose_description']}")
    if analysis.get("style_tags"):
        parts.append(f"سبک: {analysis['style_tags']}")
    return "\n".join(parts) if parts else ""
