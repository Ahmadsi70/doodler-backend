"""
Stress test suite for build_mvc_yaml_dict and generate_mvc_yaml in runpod_backend/character_utils.py.
Tests custom window dimensions, scale parameters, camera positions/vectors, and malformed/empty input parameters.
"""

import sys
import os
import traceback
import yaml

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from runpod_backend.character_utils import build_mvc_yaml_dict, generate_mvc_yaml


def run_tests():
    results = []
    
    def log_result(test_name: str, passed: bool, details: str = "", category: str = "PASS"):
        results.append({"test": test_name, "passed": passed, "details": details, "category": category})
        print(f"[{category}] {test_name}: {details}")

    print("==================================================")
    print("STRESS TEST SUITE: AnimatedDrawings MVC YAML Framing")
    print("==================================================\n")

    # ----------------------------------------------------
    # Test Suite 1: Custom Window Dimensions
    # ----------------------------------------------------
    print("--- Test Suite 1: Custom Window Dimensions ---")
    dimensions_cases = [
        ("Default (1080, 1080)", (1080, 1080)),
        ("Widescreen (1920, 1080)", (1920, 1080)),
        ("Square low-res (512, 512)", (512, 512)),
        ("Portrait (1080, 1920)", (1080, 1920)),
        ("4K (3840, 2160)", (3840, 2160)),
        ("Tiny (1, 1)", (1, 1)),
        ("Zero dimensions (0, 0)", (0, 0)),
        ("List format [1920, 1080]", [1920, 1080]),
    ]

    for name, dims in dimensions_cases:
        test_id = f"Dimensions: {name}"
        try:
            d = build_mvc_yaml_dict(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                window_dimensions=dims,
            )
            yaml_str = generate_mvc_yaml(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                window_dimensions=dims,
            )
            parsed = yaml.safe_load(yaml_str)

            win_dim = parsed["view"]["WINDOW_DIMENSIONS"]
            if win_dim == list(dims):
                log_result(test_id, True, f"Parsed WINDOW_DIMENSIONS: {win_dim}", category="PASS")
            else:
                log_result(test_id, False, f"Expected {list(dims)}, got {win_dim}", category="FAIL")
        except Exception as e:
            log_result(test_id, False, f"Exception raised: {type(e).__name__}: {e}", category="FAIL")

    # ----------------------------------------------------
    # Test Suite 2: Custom Scale Parameters
    # ----------------------------------------------------
    print("\n--- Test Suite 2: Custom Scale Parameters ---")
    scale_cases = [
        ("Default 1.0", 1.0),
        ("Downscale 0.5", 0.5),
        ("Small 0.1", 0.1),
        ("Upscale 1.5", 1.5),
        ("Upscale 2.0", 2.0),
        ("Large 10.0", 10.0),
        ("Zero scale 0.0", 0.0),
        ("Negative scale -1.0", -1.0),
        ("Integer scale 2", 2),
        ("String float '1.5'", "1.5"),
    ]

    for name, scale_val in scale_cases:
        test_id = f"Scale: {name}"
        try:
            d = build_mvc_yaml_dict(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                scale=scale_val,
            )
            yaml_str = generate_mvc_yaml(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                scale=scale_val,
            )
            parsed = yaml.safe_load(yaml_str)

            sc = parsed["scene"]["ANIMATED_CHARACTERS"][0]["scale"]
            expected = float(scale_val)
            if sc == expected and isinstance(sc, float):
                log_result(test_id, True, f"Parsed scale: {sc} (float)", category="PASS")
            else:
                log_result(test_id, False, f"Expected float {expected}, got {sc} ({type(sc).__name__})", category="FAIL")
        except Exception as e:
            log_result(test_id, False, f"Exception raised: {type(e).__name__}: {e}", category="FAIL")

    # ----------------------------------------------------
    # Test Suite 3: Custom Camera Positions & Forward Vectors
    # ----------------------------------------------------
    print("\n--- Test Suite 3: Custom Camera Positions & Forward Vectors ---")
    camera_cases = [
        ("Default pos/fwd", [0.0, 0.0, 3.5], [0.0, 0.0, -1.0]),
        ("Far pos", [0.0, 0.0, 10.0], [0.0, 0.0, -1.0]),
        ("Close pos", [0.0, 0.0, 1.0], [0.0, 0.0, -1.0]),
        ("Offset pos", [1.5, -0.5, 4.0], [0.0, 0.0, -1.0]),
        ("Angled fwd", [0.0, 0.0, 3.5], [0.1, -0.2, -0.9]),
        ("Tuple pos/fwd", (0.0, 1.0, 5.0), (0.0, 0.0, -1.0)),
        ("Negative coords", [-2.5, -3.0, -1.0], [0.0, 1.0, 0.0]),
    ]

    for name, pos, fwd in camera_cases:
        test_id = f"Camera: {name}"
        try:
            d = build_mvc_yaml_dict(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                camera_pos=pos,
                camera_fwd=fwd,
            )
            yaml_str = generate_mvc_yaml(
                character_cfg="char.yaml",
                motion_cfg="motion.yaml",
                retarget_cfg="retarget.yaml",
                output_video_path="out.mp4",
                camera_pos=pos,
                camera_fwd=fwd,
            )
            parsed = yaml.safe_load(yaml_str)

            p_pos = parsed["view"]["CAMERA_POS"]
            p_fwd = parsed["view"]["CAMERA_FWD"]
            if p_pos == list(pos) and p_fwd == list(fwd):
                log_result(test_id, True, f"CAMERA_POS={p_pos}, CAMERA_FWD={p_fwd}", category="PASS")
            else:
                log_result(test_id, False, f"Mismatch. Got pos={p_pos}, fwd={p_fwd}", category="FAIL")
        except Exception as e:
            log_result(test_id, False, f"Exception raised: {type(e).__name__}: {e}", category="FAIL")

    # ----------------------------------------------------
    # Test Suite 4: Malformed & Edge Inputs
    # ----------------------------------------------------
    print("\n--- Test Suite 4: Malformed & Edge Inputs ---")
    malformed_cases = [
        ("Empty strings for paths", "", "", "", "", {}),
        ("Special characters in paths", "C:\\Path With Spaces\\char.yaml", "motion/spec!@#.yaml", "retarget.yaml", "out_video&123.mp4", {}),
        ("Empty list camera_pos", "char.yaml", "motion.yaml", "retarget.yaml", "out.mp4", {"camera_pos": []}),
        ("Non-string scale 'abc'", "char.yaml", "motion.yaml", "retarget.yaml", "out.mp4", {"scale": "abc"}),
        ("None window_dimensions", "char.yaml", "motion.yaml", "retarget.yaml", "out.mp4", {"window_dimensions": None}),
        ("None camera_pos", "char.yaml", "motion.yaml", "retarget.yaml", "out.mp4", {"camera_pos": None}),
        ("Non-iterable window_dimensions 1080", "char.yaml", "motion.yaml", "retarget.yaml", "out.mp4", {"window_dimensions": 1080}),
    ]

    for item in malformed_cases:
        name = item[0]
        c_cfg, m_cfg, r_cfg, o_path, kwargs = item[1], item[2], item[3], item[4], item[5]
        test_id = f"Malformed: {name}"
            
        try:
            d = build_mvc_yaml_dict(c_cfg, m_cfg, r_cfg, o_path, **kwargs)
            yaml_str = generate_mvc_yaml(c_cfg, m_cfg, r_cfg, o_path, **kwargs)
            parsed = yaml.safe_load(yaml_str)
            log_result(test_id, True, f"Successfully built and parsed YAML without exception.", category="PASS")
        except (TypeError, ValueError) as e:
            log_result(test_id, False, f"Exception caught on invalid input: {type(e).__name__}: {e}", category="EXPECTED_ERROR")
        except Exception as e:
            log_result(test_id, False, f"Unexpected Exception: {type(e).__name__}: {e}", category="FAIL")

    # ----------------------------------------------------
    # Test Suite 5: YAML Structure & Parameter Integrity
    # ----------------------------------------------------
    print("\n--- Test Suite 5: YAML Structure & Parameter Integrity ---")
    struct_test_id = "Structure Integrity"
    try:
        yaml_str = generate_mvc_yaml(
            character_cfg="C:/Users/badri/char.yaml",
            motion_cfg="C:/Users/badri/motion.yaml",
            retarget_cfg="C:/Users/badri/retarget.yaml",
            output_video_path="C:/Users/badri/output.mp4",
            window_dimensions=(1920, 1080),
            camera_pos=[0.0, 1.0, 4.0],
            camera_fwd=[0.0, 0.0, -1.0],
            clear_color=[1.0, 1.0, 1.0, 1.0],
            char_starting_location=[0.0, 0.0, 0.0],
            scale=1.5,
            output_video_codec="mp4v",
            mode="video_render",
        )
        parsed = yaml.safe_load(yaml_str)

        required_keys = [
            ("view", dict),
            ("view.WINDOW_DIMENSIONS", list),
            ("view.CAMERA_POS", list),
            ("view.CAMERA_FWD", list),
            ("view.CLEAR_COLOR", list),
            ("scene", dict),
            ("scene.ANIMATED_CHARACTERS", list),
            ("controller", dict),
            ("controller.MODE", str),
            ("controller.OUTPUT_VIDEO_PATH", str),
            ("controller.OUTPUT_VIDEO_CODEC", str),
        ]

        missing = []
        for key_path, expected_type in required_keys:
            parts = key_path.split(".")
            cur = parsed
            exists = True
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    exists = False
                    break
            if not exists or not isinstance(cur, expected_type):
                missing.append(f"{key_path} (expected {expected_type.__name__}, got {type(cur).__name__} / exists={exists})")

        # Check character sub-dict
        anim_chars = parsed.get("scene", {}).get("ANIMATED_CHARACTERS", [])
        if not anim_chars or not isinstance(anim_chars[0], dict):
            missing.append("scene.ANIMATED_CHARACTERS[0] element missing")
        else:
            char_dict = anim_chars[0]
            for subkey, stype in [("character_cfg", str), ("motion_cfg", str), ("retarget_cfg", str), ("char_starting_location", list), ("scale", float)]:
                if subkey not in char_dict or not isinstance(char_dict[subkey], stype):
                    missing.append(f"scene.ANIMATED_CHARACTERS[0].{subkey} (expected {stype.__name__})")

        if missing:
            log_result(struct_test_id, False, f"Missing or invalid keys: {missing}", category="FAIL")
        else:
            log_result(struct_test_id, True, "All required sections and parameters present with correct types!", category="PASS")

    except Exception as e:
        log_result(struct_test_id, False, f"Exception during structure test: {type(e).__name__}: {e}", category="FAIL")

    # ----------------------------------------------------
    # Test Suite 6: Default Parameter Mutation Isolation
    # ----------------------------------------------------
    print("\n--- Test Suite 6: Default Parameter Mutation Isolation ---")
    mut_test_id = "Default Mutation Isolation"
    try:
        d1 = build_mvc_yaml_dict("c1.yaml", "m1.yaml", "r1.yaml", "o1.mp4")
        d1["view"]["CAMERA_POS"].append(999.0)
        d2 = build_mvc_yaml_dict("c2.yaml", "m2.yaml", "r2.yaml", "o2.mp4")
        if d2["view"]["CAMERA_POS"] == [0.0, 0.0, 3.5]:
            log_result(mut_test_id, True, "Default CAMERA_POS list instance is isolated from dict mutations.", category="PASS")
        else:
            log_result(mut_test_id, False, f"Default mutated! Got {d2['view']['CAMERA_POS']}", category="FAIL")
    except Exception as e:
        log_result(mut_test_id, False, f"Exception during mutation isolation test: {e}", category="FAIL")

    # Summary
    pass_count = sum(1 for r in results if r["category"] == "PASS")
    exp_err_count = sum(1 for r in results if r["category"] == "EXPECTED_ERROR")
    fail_count = sum(1 for r in results if r["category"] == "FAIL")
    total_count = len(results)
    
    print("\n==================================================")
    print(f"SUMMARY: Total={total_count} | Pass={pass_count} | Expected Errors on Invalid Input={exp_err_count} | Failures={fail_count}")
    print("==================================================")
    return results


if __name__ == "__main__":
    run_tests()
