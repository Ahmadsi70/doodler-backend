"""
Integration tests for server.py and handler.py character generation workflow.
Tests prompt construction and texture processing with realistic API payloads
and edge cases.
"""

import os
import tempfile
import pytest
from PIL import Image, ImageDraw

from runpod_backend.character_utils import (
    build_strict_character_prompt,
    process_character_texture,
    PREFIX_DIRECTIVE,
    SAFEGUARD_DIRECTIVE,
)
from tests.test_character_padding import verify_outer_margins_white


@pytest.fixture
def mock_char_dir(tmp_path):
    """Creates a temporary mock AnimatedDrawings character directory with char_cfg.yaml."""
    char_dir = tmp_path / "char1"
    char_dir.mkdir()
    cfg_file = char_dir / "char_cfg.yaml"
    cfg_file.write_text("width: 454\nheight: 602\n")
    return char_dir


def test_server_texture_pipeline_simulation(mock_char_dir):
    """
    Simulate the server.py character generation logic:
    1. Spec -> build_strict_character_prompt(spec)
    2. Synthetic RGBA image (simulating rembg output) -> process_character_texture(512, 512)
    3. Overriding char1 texture using char_cfg dimensions (454, 602) -> process_character_texture(454, 602)
    """
    spec = {
        "sketch": {
            "parts": [
                {"part_type": "head", "prompt": "a cute dragon head"},
                {"part_type": "body", "prompt": "scaly green body"},
            ]
        }
    }

    prompt = build_strict_character_prompt(spec)
    assert prompt.startswith(PREFIX_DIRECTIVE)
    assert "a cute dragon head" in prompt
    assert prompt.endswith(SAFEGUARD_DIRECTIVE)

    # Simulate rembg transparent output (e.g. 512x512 with character drawn inside)
    img_no_bg = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_no_bg)
    draw.rectangle([50, 50, 462, 462], fill=(0, 200, 100, 255))

    # Server Step 1: Generate char image (512x512)
    final_512 = process_character_texture(img_no_bg, target_size=(512, 512), margin=30)
    assert final_512.size == (512, 512)
    assert verify_outer_margins_white(final_512, margin=30, tolerance=0)

    # Server Step 2: Override char1 texture using char_cfg dimensions (w=454, h=602)
    w, h = 454, 602
    texture_img = process_character_texture(img_no_bg, target_size=(w, h), margin=30)
    assert texture_img.size == (454, 602)
    assert verify_outer_margins_white(texture_img, margin=30, tolerance=0)

    # Save and verify
    tex_path = mock_char_dir / "texture.png"
    texture_img.save(tex_path)
    reloaded = Image.open(tex_path)
    assert reloaded.size == (454, 602)
    assert verify_outer_margins_white(reloaded, margin=30, tolerance=2)


def test_handler_vs_server_dimension_discrepancy(mock_char_dir):
    """
    Test handler.py hardcoded target_size (512, 512) vs char_cfg.yaml (454, 602).
    Highlights discrepancy where handler saves 512x512 instead of character's configured 454x602.
    """
    img_no_bg = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_no_bg)
    draw.rectangle([100, 100, 400, 400], fill=(255, 0, 0, 255))

    # Handler logic currently uses target_size=(512, 512) ignoring char_cfg.yaml
    handler_texture = process_character_texture(img_no_bg, target_size=(512, 512), margin=30)
    assert handler_texture.size == (512, 512)

    # Server logic reads char_cfg.yaml (454, 602)
    server_texture = process_character_texture(img_no_bg, target_size=(454, 602), margin=30)
    assert server_texture.size == (454, 602)

    # Verify that handler and server output sizes differ!
    assert handler_texture.size != server_texture.size
