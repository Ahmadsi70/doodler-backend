"""
Comprehensive stress tests and edge case verification for character_utils.py,
server.py, and handler.py integration.
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
from tests.test_character_padding import verify_outer_margins_white


# ============================================================================
# 1. PROMPT FORMATTING & SPEC EDGE CASES (CRASH & NULL TEST CASES)
# ============================================================================

def test_prompt_null_sketch_raises_or_handles():
    """Verify that build_strict_character_prompt handles {'sketch': None} without AttributeError."""
    # When spec has "sketch": None (valid JSON null), spec.get("sketch", {}) returns None,
    # causing None.get("parts", []) to raise AttributeError.
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
        build_strict_character_prompt({"sketch": None})


def test_prompt_null_parts_raises_or_handles():
    """Verify that build_strict_character_prompt handles {'sketch': {'parts': None}} without TypeError."""
    # When spec has parts: None, for p in parts attempts iteration over NoneType.
    with pytest.raises(TypeError, match="'NoneType' object is not iterable"):
        build_strict_character_prompt({"sketch": {"parts": None}})


def test_prompt_null_brief_raises_or_handles():
    """Verify that build_strict_character_prompt handles {'brief': None} without AttributeError."""
    # When spec has "brief": None and no sketch/parts/character_prompt/prompt,
    # spec.get("brief", {}).get("user_prompt") calls .get on None.
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
        build_strict_character_prompt({"brief": None})


def test_prompt_empty_and_whitespace_prompts():
    """Test handling of empty strings, spaces, and None values inside parts array."""
    spec = {
        "sketch": {
            "parts": [
                {"part_type": "head", "prompt": ""},
                {"part_type": "body", "prompt": "   "},
                {"part_type": "arms", "prompt": None},
                {"part_type": "legs", "prompt": "  slender legs  "},
                None,
                "not a dict",
                {"no_prompt_key": "val"},
            ]
        }
    }
    prompt = build_strict_character_prompt(spec)
    assert "slender legs" in prompt
    assert prompt.startswith(PREFIX_DIRECTIVE)
    assert prompt.endswith(SAFEGUARD_DIRECTIVE)


def test_prompt_non_dict_inputs():
    """Test robustness when non-dict objects are passed as spec."""
    for invalid_spec in [None, "string_spec", 12345, [1, 2, 3], True]:
        prompt = build_strict_character_prompt(invalid_spec)
        assert prompt.startswith(PREFIX_DIRECTIVE)
        assert prompt.endswith(SAFEGUARD_DIRECTIVE)
        assert "character design" in prompt


def test_prompt_precedence_and_fallbacks():
    """Verify fallback precedence: sketch.parts -> character_prompt -> prompt -> brief.user_prompt."""
    # 1. sketch.parts valid -> uses sketch.parts
    spec1 = {
        "sketch": {"parts": [{"prompt": "head prompt"}]},
        "character_prompt": "char prompt",
        "prompt": "general prompt",
        "brief": {"user_prompt": "brief prompt"},
    }
    p1 = build_strict_character_prompt(spec1)
    assert "head prompt" in p1
    assert "char prompt" not in p1

    # 2. sketch.parts empty -> uses character_prompt
    spec2 = {
        "sketch": {"parts": []},
        "character_prompt": "char prompt",
        "prompt": "general prompt",
        "brief": {"user_prompt": "brief prompt"},
    }
    p2 = build_strict_character_prompt(spec2)
    assert "char prompt" in p2
    assert "general prompt" not in p2

    # 3. sketch empty & character_prompt empty -> uses prompt
    spec3 = {
        "prompt": "general prompt",
        "brief": {"user_prompt": "brief prompt"},
    }
    p3 = build_strict_character_prompt(spec3)
    assert "general prompt" in p3
    assert "brief prompt" not in p3

    # 4. prompt empty -> uses brief.user_prompt
    spec4 = {
        "brief": {"user_prompt": "brief prompt"},
    }
    p4 = build_strict_character_prompt(spec4)
    assert "brief prompt" in p4

    # 5. everything empty -> falls back to "character design"
    spec5 = {"sketch": {"parts": [{"prompt": ""}]}, "character_prompt": "", "prompt": ""}
    p5 = build_strict_character_prompt(spec5)
    assert "character design" in p5


def test_prompt_special_characters_and_unicode():
    """Test prompt formatting with special characters, unicode, emojis, and punctuation."""
    spec = {
        "sketch": {
            "parts": [
                {"prompt": "robot with 'cool' gear! & #1 head,"},
                {"prompt": "⚡ magical aura ✨, \n\t newline test."},
                {"prompt": 'quotes "double" and \\ backslash'},
            ]
        }
    }
    prompt = build_strict_character_prompt(spec)
    assert "robot with 'cool' gear! & #1 head" in prompt
    assert "⚡ magical aura ✨" in prompt
    assert prompt.startswith(PREFIX_DIRECTIVE)
    assert prompt.endswith(SAFEGUARD_DIRECTIVE)


def test_prompt_extreme_long_text_and_many_parts():
    """Test performance and output with huge prompt texts and 500 parts."""
    long_str = "x" * 5000
    many_parts = [{"prompt": f"part_{i} {long_str if i == 0 else ''}"} for i in range(500)]
    spec = {"sketch": {"parts": many_parts}}

    prompt = build_strict_character_prompt(spec)
    assert prompt.startswith(PREFIX_DIRECTIVE)
    assert prompt.endswith(SAFEGUARD_DIRECTIVE)
    assert "part_0" in prompt
    assert "part_499" in prompt


# ============================================================================
# 2. TEXTURE PROCESSING & IMAGE EDGE CASES
# ============================================================================

def test_texture_image_modes():
    """Test process_character_texture across different PIL image modes (RGB, L, P, CMYK, LA)."""
    modes = ["RGB", "L", "P", "CMYK", "LA"]
    for mode in modes:
        if mode == "P":
            img = Image.new("RGBA", (100, 100), (255, 0, 0, 255)).convert("P")
        else:
            img = Image.new(mode, (100, 100))
        
        res = process_character_texture(img, target_size=(512, 512), margin=30)
        assert res.size == (512, 512)
        assert verify_outer_margins_white(res, margin=30, tolerance=2)


def test_texture_extreme_dimensions():
    """Test texture processing with 1x1 image, very high aspect ratio, and custom target size (454, 602)."""
    # 1x1 pixel image
    img1 = Image.new("RGBA", (1, 1), (255, 0, 0, 255))
    res1 = process_character_texture(img1, target_size=(512, 512), margin=30)
    assert res1.size == (512, 512)
    assert verify_outer_margins_white(res1, margin=30, tolerance=0)

    # 454x602 target size (AnimatedDrawings char1 default dimensions)
    img_char1 = Image.new("RGBA", (300, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_char1)
    draw.rectangle([0, 0, 300, 500], fill=(0, 100, 200, 255))
    res_char1 = process_character_texture(img_char1, target_size=(454, 602), margin=30)
    assert res_char1.size == (454, 602)
    assert verify_outer_margins_white(res_char1, margin=30, tolerance=0)

    # Extremely wide (2000 x 50)
    img_wide = Image.new("RGBA", (2000, 50), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_wide)
    draw.rectangle([0, 0, 2000, 50], fill=(100, 200, 0, 255))
    res_wide = process_character_texture(img_wide, target_size=(512, 512), margin=30)
    assert res_wide.size == (512, 512)
    assert verify_outer_margins_white(res_wide, margin=30, tolerance=0)


def test_texture_margin_edge_cases():
    """Test process_character_texture with zero margin and large margin."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 190], fill=(255, 0, 0, 255))

    # Margin 0
    res_m0 = process_character_texture(img, target_size=(512, 512), margin=0)
    assert res_m0.size == (512, 512)

    # Large margin 200 (leaving 112x112 central area)
    res_m200 = process_character_texture(img, target_size=(512, 512), margin=200)
    assert res_m200.size == (512, 512)
    assert verify_outer_margins_white(res_m200, margin=200, tolerance=0)


def test_texture_semi_transparent_alpha():
    """Test process_character_texture with semi-transparent pixels."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 200, 200], fill=(255, 0, 0, 128))

    res = process_character_texture(img, target_size=(512, 512), margin=30)
    assert res.size == (512, 512)
    assert verify_outer_margins_white(res, margin=30, tolerance=0)
