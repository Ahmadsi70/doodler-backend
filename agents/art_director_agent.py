"""
ArtDirectorAgent — generates production-ready text-to-image prompts
(Midjourney / SDXL / DALL-E 3) that guarantee visual consistency across
all shots using character description + storyboard metadata.
"""

from __future__ import annotations

import json
from typing import Any

_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "cinematic": {
        "art_style": "cinematic, film grain, anamorphic lens, dramatic lighting, 35mm photography",
        "negative": "cartoon, illustration, 3d render, anime, painting, sketch, low resolution, blurry",
        "model_hint": "--ar 16:9 --style raw --v 6.1",
    },
    "anime": {
        "art_style": "anime style, studio ghibli inspired, cel shaded, hand-drawn aesthetic, soft gradients",
        "negative": "photorealistic, 3d render, live action, film grain, cinematic",
        "model_hint": "--ar 16:9 --niji 6",
    },
    "illustration": {
        "art_style": "digital illustration, concept art, painterly, detailed background, smooth shading",
        "negative": "photograph, 3d render, low detail, blurry, grainy",
        "model_hint": "--ar 16:9 --style expressive --v 6.1",
    },
    "pixelart": {
        "art_style": "pixel art, retro game, 16-bit, limited palette, chunky pixels",
        "negative": "smooth gradient, realistic, 3d, blur, anti-aliasing, photograph",
        "model_hint": "--ar 16:9 --style cute --v 6.1",
    },
    "stop_motion": {
        "art_style": "stop motion, claymation, tactile materials, visible fingerprints, plasticine texture",
        "negative": "smooth cgi, realistic rendering, digital, clean lines",
        "model_hint": "--ar 16:9 --v 6.1",
    },
}

_DEFAULT_CHARACTER_SEED = 42


def run_art_director_agent(
    storyboard: dict[str, Any],
    *,
    character_description: str = "",
    character_analysis: dict[str, Any] | None = None,
    style_id: str = "cinematic",
    palette_override: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate per-shot T2I prompts from storyboard + character data.

    Returns structured JSON with:
      - global_style: art style, palette, character seed, negative prompts
      - shots: per-shot prompts optimized for Midjourney, SDXL, DALL-E 3
    """
    style = _STYLE_PRESETS.get(style_id, _STYLE_PRESETS["cinematic"])
    shots_in = storyboard.get("shots") or []

    # Extract character traits
    char_name = "Main Character"
    char_physical = ""
    char_clothing = ""
    char_colors: list[str] = []

    if character_analysis:
        char_name = character_analysis.get("name", "Main Character")
        char_physical = _describe_field(character_analysis, ["physical_description", "facial_features"])
        char_clothing = _describe_field(character_analysis, ["clothing", "clothing_description"])
        char_colors = character_analysis.get("dominant_colors") or character_analysis.get("color_palette") or []
    elif character_description:
        char_physical = character_description

    # Derive palette from character colors or style
    palette = palette_override or char_colors[:5] or _palette_for_style(style_id)

    # Character seed for consistency
    char_seed = _character_seed_from_description(character_description or char_physical)

    # Build per-shot prompts
    shots_out: list[dict[str, Any]] = []
    for sh in shots_in:
        sid = sh.get("shot_id", sh.get("shotId", 0))
        action = sh.get("action") or sh.get("idea") or ""
        beat = sh.get("story_beat") or ""
        composition = sh.get("composition_shape") or sh.get("composition") or "C"
        shot_size = sh.get("shot_size") or sh.get("shotSize") or "MS"
        lighting = sh.get("lighting") or "three_point"
        camera = sh.get("camera") or "static"
        lens = sh.get("lens") or "standard"
        pose = sh.get("pose") or "idle"
        expression = sh.get("expression") or "neutral"

        # Compose subject description
        subject = char_name
        if char_physical:
            subject += f", {char_physical}"
        if char_clothing:
            subject += f", wearing {char_clothing}"
        if pose:
            subject += f", {pose} pose"
        if expression:
            subject += f", {expression} expression"

        composition_desc = _composition_description(composition, shot_size)
        lighting_desc = _lighting_description(lighting)
        camera_desc = _camera_description(camera, lens)
        mood_desc = _mood_for_beat(beat)

        # -- Midjourney prompt --
        midjourney_prompt = (
            f"{subject}, {action}"
            f" -- {composition_desc}, {shot_size} shot"
            f", {camera_desc}, {lighting_desc}"
            f", {mood_desc}"
            f", {style['art_style']}"
            f" --sref {_style_code(style_id)}"
            f" --seed {char_seed} {style['model_hint']}"
        )

        # -- SDXL prompt --
        sdxl_prompt = (
            f"{subject} {action}, {composition_desc}, {shot_size} view, "
            f"{camera_desc}, {lighting_desc}, {mood_desc}, "
            f"{style['art_style']}, {', '.join(palette)} palette"
        )
        sdxl_negative = (
            f"{style['negative']}, inconsistent character, deformed, extra limbs, "
            f"bad anatomy, ugly, disfigured"
        )

        # -- DALL-E 3 prompt --
        dalle_prompt = (
            f"{subject}. {action}. "
            f"Shot: {shot_size}, Camera: {camera_desc}, Lighting: {lighting_desc}. "
            f"Style: {style['art_style']}. "
            f"Color palette: {', '.join(palette)}."
            f" Mood: {mood_desc}."
        )

        shots_out.append({
            "shotId": sid,
            "character_seed": char_seed,
            "prompts": {
                "midjourney": midjourney_prompt,
                "sdxl": sdxl_prompt,
                "dalle3": dalle_prompt,
            },
            "negative_prompt": sdxl_negative,
            "subject": subject,
            "composition": composition_desc,
            "shot_size": shot_size,
            "lighting": lighting_desc,
            "camera": camera_desc,
            "mood": mood_desc,
        })

    result = {
        "schema": "art_director#v1",
        "style_id": style_id,
        "character_name": char_name,
        "character_seed": char_seed,
        "palette": palette,
        "art_style": style["art_style"],
        "global_negative_prompt": style["negative"],
        "model_hints": {
            "midjourney": style["model_hint"],
            "sdxl": "--ar 16:9",
            "dalle3": "16:9 widescreen",
        },
        "shots": shots_out,
    }

    return result


# ── helpers ────────────────────────────────────────────────────────────


def _describe_field(analysis: dict[str, Any], keys: list[str]) -> str:
    for k in keys:
        v = analysis.get(k)
        if v and isinstance(v, str):
            return v.strip()
        if v and isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
    return ""


def _character_seed_from_description(desc: str) -> int:
    import hashlib
    return int(hashlib.md5((desc or "default").encode()).hexdigest()[:8], 16) % 100000


def _palette_for_style(style_id: str) -> list[str]:
    presets: dict[str, list[str]] = {
        "cinematic": ["deep teal", "warm amber", "cool gray", "pure white"],
        "anime": ["pastel pink", "sky blue", "soft white", "lavender"],
        "illustration": ["vibrant orange", "forest green", "cream", "slate"],
        "pixelart": ["neon cyan", "hot pink", "dark purple", "pixel white"],
        "stop_motion": ["muted clay", "wool gray", "faded red", "off white"],
    }
    return presets.get(style_id, presets["cinematic"])


def _style_code(style_id: str) -> str:
    codes = {
        "cinematic": "1658694732",
        "anime": "3695215487",
        "illustration": "2853746190",
        "pixelart": "7418529630",
        "stop_motion": "5847362910",
    }
    return codes.get(style_id, codes["cinematic"])


def _composition_description(composition: str, shot_size: str) -> str:
    comp = (composition or "C").upper()[:1]
    size = shot_size.upper()
    if comp == "L":
        return f"subject positioned on left third, {size} composition, rule of thirds"
    if comp == "R":
        return f"subject positioned on right third, {size} composition, rule of thirds"
    return f"subject centered, {size} composition, symmetric framing"


def _lighting_description(lighting: str) -> str:
    descs = {
        "three_point": "three-point lighting, soft key light, subtle fill, rim light",
        "rim": "rim lighting, dramatic backlight, silhouetted edges",
        "practical": "practical lighting, warm ambient sources, motivated light",
        "natural": "natural lighting, soft diffused daylight, gentle shadows",
        "hard": "hard lighting, strong shadows, high contrast, noir style",
        "soft": "soft lighting, diffused, gentle gradients, low contrast",
        "moody": "moody lighting, low key, deep shadows, atmospheric",
        "silhouette": "silhouette lighting, backlit, dark foreground, bright background",
    }
    return descs.get(lighting.lower(), f"{lighting} lighting")


def _camera_description(camera: str, lens: str) -> str:
    descs = {
        "static": "locked-off camera, static frame",
        "pan": "panning camera, horizontal movement",
        "tilt": "tilting camera, vertical movement",
        "dolly": "dolly camera, smooth tracking movement",
        "track": "tracking camera, lateral movement",
        "crane": "crane shot, vertical elevation",
        "aerial": "aerial view, top-down perspective",
    }
    cam_desc = descs.get(camera.lower(), f"{camera} camera movement")

    lens_descs = {
        "standard": "50mm equivalent lens",
        "wide": "24mm wide-angle lens",
        "telephoto": "85mm telephoto lens, compressed perspective",
        "fisheye": "fisheye lens, extreme wide angle, distortion",
        "macro": "macro lens, extreme close-up detail",
        "anamorphic": "anamorphic lens, wide cinemascope, lens flares",
    }
    lens_desc = lens_descs.get(lens.lower(), f"{lens} lens")

    return f"{cam_desc}, {lens_desc}"


def _mood_for_beat(beat: str) -> str:
    moods = {
        "entrance": "grand, hopeful, establishing",
        "exit": "bittersweet, reflective, closing",
        "reaction": "surprised, emotional, intense",
        "reveal": "dramatic, awe-inspiring, wondrous",
        "quiet_hold": "peaceful, intimate, contemplative",
        "conflict": "tense, aggressive, confrontational",
        "decision": "determined, resolute, focused",
        "default": "neutral, balanced, observed",
    }
    return moods.get(beat.lower() if beat else "", moods["default"])
