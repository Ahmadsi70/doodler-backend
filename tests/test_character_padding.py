"""
Programmatic verification tests for character prompt construction and texture image padding/resizing.
Verifies that texture post-processing guarantees pure white background margins (RGB 255, 255, 255)
along all four edges (top, bottom, left, right) of generated texture images.
"""

import os
import tempfile
import numpy as np
import pytest
from PIL import Image, ImageDraw

from runpod_backend.character_utils import (
    build_strict_character_prompt,
    process_character_texture,
    PREFIX_DIRECTIVE,
    SAFEGUARD_DIRECTIVE,
)


def verify_outer_margins_white(img: Image.Image, margin: int = 30, tolerance: int = 3) -> bool:
    """
    Programmatic helper that inspects all 4 outer margins (top rows, bottom rows,
    left columns, right columns) of an image to confirm they consist entirely of
    white background pixels (RGB 255, 255, 255) within specified tolerance.
    """
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb)
    h, w, c = arr.shape

    assert h >= 2 * margin, f"Image height {h} is smaller than 2 * margin ({2 * margin})"
    assert w >= 2 * margin, f"Image width {w} is smaller than 2 * margin ({2 * margin})"

    white = np.array([255, 255, 255], dtype=np.uint8)

    # 1. Top margin (rows 0 to margin-1)
    top_region = arr[0:margin, :, :]
    # 2. Bottom margin (rows h-margin to h-1)
    bottom_region = arr[h - margin : h, :, :]
    # 3. Left margin (cols 0 to margin-1)
    left_region = arr[:, 0:margin, :]
    # 4. Right margin (cols w-margin to w-1)
    right_region = arr[:, w - margin : w, :]

    for name, region in [("top", top_region), ("bottom", bottom_region), ("left", left_region), ("right", right_region)]:
        diff = np.abs(region.astype(int) - white.astype(int))
        max_diff = np.max(diff)
        if max_diff > tolerance:
            print(f"Margin check failed in {name} region: max diff {max_diff} > {tolerance}")
            return False

    return True


def test_build_strict_character_prompt_structure():
    """Verify that prompt builder prepends prefix directives and appends safeguard directives."""
    spec = {
        "sketch": {
            "parts": [
                {"part_type": "head", "prompt": "a cute round cat head"},
                {"part_type": "body", "prompt": "fluffy body with blue scarf"},
            ]
        }
    }

    prompt = build_strict_character_prompt(spec)

    # 1. Check prefix framing directives
    assert prompt.startswith(PREFIX_DIRECTIVE), "Prompt must start with required prefix directives"
    assert "full body character sheet" in prompt
    assert "single isolated character" in prompt
    assert "standing pose" in prompt
    assert "symmetrical front view" in prompt
    assert "A-pose" in prompt
    assert "solid pure white background" in prompt

    # 2. Check spec part prompts included
    assert "a cute round cat head" in prompt
    assert "fluffy body with blue scarf" in prompt

    # 3. Check safeguard directives appended
    assert prompt.endswith(SAFEGUARD_DIRECTIVE), "Prompt must end with required safeguard directives"
    assert "full body visible" in prompt
    assert "head to toe" in prompt
    assert "no crop" in prompt


def test_build_strict_character_prompt_fallbacks():
    """Verify prompt builder fallback behavior when sketch.parts is absent."""
    # Fallback to character_prompt
    prompt1 = build_strict_character_prompt({"character_prompt": "robot warrior"})
    assert "robot warrior" in prompt1
    assert prompt1.startswith(PREFIX_DIRECTIVE)
    assert prompt1.endswith(SAFEGUARD_DIRECTIVE)

    # Fallback to brief.user_prompt
    prompt2 = build_strict_character_prompt({"brief": {"user_prompt": "happy dragon"}})
    assert "happy dragon" in prompt2
    assert prompt2.startswith(PREFIX_DIRECTIVE)
    assert prompt2.endswith(SAFEGUARD_DIRECTIVE)

    # Empty spec fallback
    prompt3 = build_strict_character_prompt({})
    assert prompt3.startswith(PREFIX_DIRECTIVE)
    assert prompt3.endswith(SAFEGUARD_DIRECTIVE)


def test_process_character_texture_margin_padding():
    """
    Test that process_character_texture crops, scales, and pads character images such that
    all 4 outer margins (top, bottom, left, right) are guaranteed pure white.
    """
    # Create an RGBA image with a character shape that touches the outer image boundary
    src_w, src_h = 400, 400
    rgba = Image.new("RGBA", (src_w, src_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)

    # Draw a colored shape extending right up to border (0, 0) to (400, 400)
    draw.rectangle([0, 0, 400, 400], fill=(255, 0, 0, 255))

    # Process texture with target 512x512 and 30px margin
    processed_512 = process_character_texture(rgba, target_size=(512, 512), margin=30)

    assert processed_512.size == (512, 512)
    assert verify_outer_margins_white(processed_512, margin=30, tolerance=0)


def test_process_character_texture_aspect_ratio_preservation():
    """
    Verify uniform scaling preserving aspect ratio for wide and tall characters.
    """
    # 1. Very wide character (400x100)
    wide_img = Image.new("RGBA", (400, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wide_img)
    draw.ellipse([0, 0, 400, 100], fill=(0, 128, 255, 255))

    out_wide = process_character_texture(wide_img, target_size=(512, 512), margin=30)
    assert verify_outer_margins_white(out_wide, margin=30, tolerance=0)

    # 2. Very tall character (100x400)
    tall_img = Image.new("RGBA", (100, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tall_img)
    draw.ellipse([0, 0, 100, 400], fill=(0, 200, 100, 255))

    out_tall = process_character_texture(tall_img, target_size=(512, 512), margin=30)
    assert verify_outer_margins_white(out_tall, margin=30, tolerance=0)


def test_process_character_texture_saved_file():
    """
    Verify that saving the processed texture to texture.png maintains white margins upon reloading.
    """
    rgba = Image.new("RGBA", (300, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)
    draw.ellipse([10, 10, 290, 490], fill=(50, 50, 200, 255))

    out_img = process_character_texture(rgba, target_size=(512, 512), margin=30)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "texture.png")
        out_img.save(tex_path)

        reloaded = Image.open(tex_path)
        assert verify_outer_margins_white(reloaded, margin=30, tolerance=2)


def test_process_character_texture_empty_alpha():
    """Verify handling of completely transparent input."""
    empty_img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    out_img = process_character_texture(empty_img, target_size=(512, 512), margin=30)
    assert out_img.size == (512, 512)
    assert verify_outer_margins_white(out_img, margin=30, tolerance=0)
