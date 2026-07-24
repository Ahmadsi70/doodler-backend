"""
Stress test harness for `process_character_texture` and `build_strict_character_prompt`
in `runpod_backend/character_utils.py`.
"""

import sys
import os
import random
import numpy as np
from PIL import Image

# Ensure repository root is in sys.path
REPO_ROOT = r"c:\Users\badri\Story"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from runpod_backend.character_utils import process_character_texture, build_strict_character_prompt, PREFIX_DIRECTIVE, SAFEGUARD_DIRECTIVE


def check_margins_pure_white(img: Image.Image, margin: int) -> tuple[bool, str]:
    """
    Verifies that all 4 outer margins (top, bottom, left, right) of size `margin` pixels
    are 100% pure white (255, 255, 255).
    """
    if margin <= 0:
        return True, "Margin is <= 0, no margin area to check."
        
    arr = np.array(img)  # Shape (H, W, 3)
    H, W, C = arr.shape
    
    if margin >= W // 2 or margin >= H // 2:
        # High margin - verify non-white pixels don't bleed past target_w-margin or target_h-margin
        pass

    # Top margin: rows 0 to margin-1
    top = arr[0:margin, :, :]
    if not np.all(top == 255):
        min_val = top.min()
        return False, f"Top margin contains non-white pixels (min val: {min_val})."

    # Bottom margin: rows H-margin to H-1
    bottom = arr[H-margin:H, :, :]
    if not np.all(bottom == 255):
        min_val = bottom.min()
        return False, f"Bottom margin contains non-white pixels (min val: {min_val})."

    # Left margin: cols 0 to margin-1
    left = arr[:, 0:margin, :]
    if not np.all(left == 255):
        min_val = left.min()
        return False, f"Left margin contains non-white pixels (min val: {min_val})."

    # Right margin: cols W-margin to W-1
    right = arr[:, W-margin:W, :]
    if not np.all(right == 255):
        min_val = right.min()
        return False, f"Right margin contains non-white pixels (min val: {min_val})."

    return True, "All 4 margins are 100% pure white."


def verify_centering(img: Image.Image) -> tuple[bool, str, dict]:
    """
    Finds the bounding box of non-white (content) pixels in the processed image,
    and checks if the content is centered within 1 pixel tolerance.
    """
    arr = np.array(img)
    H, W, _ = arr.shape
    
    # Non-white pixels mask
    non_white_mask = np.any(arr != 255, axis=2)
    coords = np.argwhere(non_white_mask)
    
    if len(coords) == 0:
        return True, "Image is entirely white (blank content).", {"blank": True}

    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)

    content_w = x_max - x_min + 1
    content_h = y_max - y_min + 1

    left_pad = x_min
    right_pad = W - 1 - x_max
    top_pad = y_min
    bottom_pad = H - 1 - y_max

    h_diff = abs(left_pad - right_pad)
    v_diff = abs(top_pad - bottom_pad)

    stats = {
        "content_size": (content_w, content_h),
        "left_pad": left_pad,
        "right_pad": right_pad,
        "top_pad": top_pad,
        "bottom_pad": bottom_pad,
        "h_diff": h_diff,
        "v_diff": v_diff
    }

    # Centering tolerance: floor division remainder can cause at most 1 pixel difference
    is_centered = (h_diff <= 1) and (v_diff <= 1)
    msg = f"H-pad: left={left_pad}, right={right_pad} (diff={h_diff}); V-pad: top={top_pad}, bottom={bottom_pad} (diff={v_diff})"

    return is_centered, msg, stats


def test_single_corner_pixel():
    print("\n--- Test 1: Single Non-Transparent Pixel at Corners ---")
    sizes = [(500, 500), (100, 300), (400, 200)]
    corners = [(0, 0), (0, "max_y"), ("max_x", 0), ("max_x", "max_y")]
    
    passed = 0
    total = 0

    for w, h in sizes:
        for cx_raw, cy_raw in corners:
            total += 1
            cx = 0 if cx_raw == 0 else w - 1
            cy = 0 if cy_raw == 0 else h - 1

            # Create transparent image with 1 red pixel
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            img.putpixel((cx, cy), (255, 0, 0, 255))

            target_size = (512, 512)
            margin = 30
            res = process_character_texture(img, target_size=target_size, margin=margin)

            white_ok, white_msg = check_margins_pure_white(res, margin)
            center_ok, center_msg, stats = verify_centering(res)

            if white_ok and center_ok:
                passed += 1
            else:
                print(f"FAILED for input size ({w},{h}), pixel at ({cx},{cy}): {white_msg} | {center_msg}")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Single corner pixel test failed!"


def test_fully_opaque():
    print("\n--- Test 2: Fully Opaque Images ---")
    sizes = [(100, 100), (500, 500), (1024, 1024), (200, 800)]
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 0, 255), (128, 128, 128, 255)]

    passed = 0
    total = 0

    for w, h in sizes:
        for c in colors:
            total += 1
            img = Image.new("RGBA", (w, h), c)
            target_size = (512, 512)
            margin = 30
            res = process_character_texture(img, target_size=target_size, margin=margin)

            white_ok, white_msg = check_margins_pure_white(res, margin)
            center_ok, center_msg, stats = verify_centering(res)

            if white_ok and center_ok:
                passed += 1
            else:
                print(f"FAILED for input size ({w},{h}): {white_msg} | {center_msg}")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Fully opaque test failed!"


def test_fully_transparent():
    print("\n--- Test 3: Fully Transparent Images ---")
    sizes = [(100, 100), (512, 512), (1000, 200)]

    passed = 0
    total = 0

    for w, h in sizes:
        total += 1
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        target_size = (512, 512)
        margin = 30
        res = process_character_texture(img, target_size=target_size, margin=margin)

        arr = np.array(res)
        is_all_white = np.all(arr == 255)

        if is_all_white:
            passed += 1
        else:
            print(f"FAILED for transparent image ({w},{h}): contains non-white pixels.")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Fully transparent test failed!"


def test_extreme_ratios():
    print("\n--- Test 4: Extreme Aspect Ratios ---")
    ratios = [(100, 1), (1, 100), (1000, 1), (1, 1000), (5000, 10), (10, 5000)]

    passed = 0
    total = 0

    for w, h in ratios:
        total += 1
        img = Image.new("RGBA", (w, h), (0, 0, 255, 255))
        target_size = (512, 512)
        margin = 30
        res = process_character_texture(img, target_size=target_size, margin=margin)

        white_ok, white_msg = check_margins_pure_white(res, margin)
        center_ok, center_msg, stats = verify_centering(res)

        if white_ok and center_ok:
            passed += 1
        else:
            print(f"FAILED for ratio ({w},{h}): {white_msg} | {center_msg}")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Extreme aspect ratio test failed!"


def test_target_canvas_and_margins():
    print("\n--- Test 5: Various Target Canvas Sizes and Margins ---")
    targets = [(256, 256), (512, 512), (1024, 1024), (300, 600)]
    margins = [0, 10, 30, 50, 100, 250]

    passed = 0
    total = 0

    for tw, th in targets:
        for m in margins:
            total += 1
            # 200x200 square image
            img = Image.new("RGBA", (200, 200), (255, 128, 0, 255))
            res = process_character_texture(img, target_size=(tw, th), margin=m)

            white_ok, white_msg = check_margins_pure_white(res, m)
            center_ok, center_msg, stats = verify_centering(res)

            if white_ok and center_ok:
                passed += 1
            else:
                print(f"FAILED for target ({tw},{th}) margin {m}: {white_msg} | {center_msg}")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Target canvas and margin variation test failed!"


def test_float_rounding_precision():
    print("\n--- Test 6: Mathematical Scaling & Rounding Precision Stress Test (100,000 combinations) ---")
    # Generates 100,000 random crop sizes and target size combinations
    # Checks if int(round(crop_w * scale)) could ever exceed max_w or bleed into margin by 1px
    
    passed = 0
    total = 100000
    
    random.seed(42)
    for _ in range(total):
        crop_w = random.randint(1, 4000)
        crop_h = random.randint(1, 4000)
        target_w = random.choice([256, 512, 1024, 768, 1920])
        target_h = random.choice([256, 512, 1024, 768, 1080])
        margin = random.randint(0, 100)
        
        max_w = max(1, target_w - 2 * margin)
        max_h = max(1, target_h - 2 * margin)
        
        scale = min(max_w / crop_w, max_h / crop_h)
        new_w = max(1, int(round(crop_w * scale)))
        new_h = max(1, int(round(crop_h * scale)))
        
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2

        # Check bounds
        if new_w > max_w:
            print(f"ROUNDING ERROR: new_w {new_w} > max_w {max_w} for crop ({crop_w},{crop_h}), target ({target_w},{target_h}), margin {margin}")
            break
        if new_h > max_h:
            print(f"ROUNDING ERROR: new_h {new_h} > max_h {max_h} for crop ({crop_w},{crop_h}), target ({target_w},{target_h}), margin {margin}")
            break
        if margin > 0 and (offset_x < margin or offset_y < margin):
            print(f"OFFSET ERROR: offset_x={offset_x}, offset_y={offset_y} < margin={margin}")
            break
        if margin > 0 and (offset_x + new_w > target_w - margin or offset_y + new_h > target_h - margin):
            print(f"BLEED ERROR: offset_x+new_w={offset_x+new_w} > {target_w-margin} or offset_y+new_h={offset_y+new_h} > {target_h-margin}")
            break
            
        passed += 1

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Precision stress test failed!"


def test_build_strict_character_prompt():
    print("\n--- Test 7: build_strict_character_prompt Verification ---")
    
    test_cases = [
        (
            {"sketch": {"parts": [{"prompt": "a blue robot warrior"}, {"prompt": "wearing golden armor"}]}},
            f"{PREFIX_DIRECTIVE}, a blue robot warrior, wearing golden armor, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"character_prompt": "a cute red panda wizard"},
            f"{PREFIX_DIRECTIVE}, a cute red panda wizard, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"prompt": "space explorer with helmet"},
            f"{PREFIX_DIRECTIVE}, space explorer with helmet, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"brief": {"user_prompt": "cyberpunk detective"}},
            f"{PREFIX_DIRECTIVE}, cyberpunk detective, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {},
            f"{PREFIX_DIRECTIVE}, character design, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            None,
            f"{PREFIX_DIRECTIVE}, character design, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"sketch": {"parts": [{"prompt": "  "}, {"prompt": "dark knight."}]}},
            f"{PREFIX_DIRECTIVE}, dark knight, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"sketch": {"parts": "not_a_list"}},
            f"{PREFIX_DIRECTIVE}, character design, {SAFEGUARD_DIRECTIVE}"
        ),
        (
            {"sketch": {"parts": [{"prompt": 12345}]}},
            f"{PREFIX_DIRECTIVE}, 12345, {SAFEGUARD_DIRECTIVE}"
        )
    ]

    passed = 0
    total = len(test_cases)

    for spec, expected in test_cases:
        result = build_strict_character_prompt(spec)
        if result == expected:
            passed += 1
        else:
            print(f"PROMPT MISMATCH:\n  Spec: {spec}\n  Got:      '{result}'\n  Expected: '{expected}'")

    print(f"Result: {passed}/{total} passed.")
    assert passed == total, "Prompt construction verification failed!"


def run_all():
    print("==========================================================")
    print("RUNNING DOODLER AI CHARACTER UTILS EMPIRICAL STRESS TESTS")
    print("==========================================================")
    test_single_corner_pixel()
    test_fully_opaque()
    test_fully_transparent()
    test_extreme_ratios()
    test_target_canvas_and_margins()
    test_float_rounding_precision()
    test_build_strict_character_prompt()
    print("\n==========================================================")
    print("ALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
    print("==========================================================")


if __name__ == "__main__":
    run_all()
