"""
Empirical Stress Test Harness for generate_mvc_yaml integration in server.py and handler.py.
Created by Challenger agent challenger_m2_2 for Milestone 2 (R2).
"""

import sys
import os
import ast
import yaml
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runpod_backend.character_utils import build_mvc_yaml_dict, generate_mvc_yaml


def test_server_and_handler_imports_and_usage():
    """Verify that server.py and handler.py import and invoke generate_mvc_yaml."""
    server_path = PROJECT_ROOT / "runpod_backend" / "server.py"
    handler_path = PROJECT_ROOT / "runpod_backend" / "handler.py"

    for filepath, name in [(server_path, "server.py"), (handler_path, "handler.py")]:
        assert filepath.exists(), f"{name} does not exist at {filepath}"
        content = filepath.read_text(encoding="utf-8")
        
        # Parse AST to ensure syntax validity and check generate_mvc_yaml usage
        tree = ast.parse(content, filename=str(filepath))
        
        # Check import
        assert "generate_mvc_yaml" in content, f"{name} does not reference 'generate_mvc_yaml'"
        
        # Check call site
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "generate_mvc_yaml"]
        assert len(calls) > 0, f"{name} does not call generate_mvc_yaml"
        print(f"[PASS] {name} imports and calls generate_mvc_yaml ({len(calls)} call site(s) found)")


def test_standard_mvc_yaml_generation_and_parsing():
    """Verify standard generate_mvc_yaml call produces valid YAML with all required sections."""
    yaml_str = generate_mvc_yaml(
        character_cfg="/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml",
        motion_cfg="/workspace/AnimatedDrawings/examples/config/motion/jumping.yaml",
        retarget_cfg="/workspace/AnimatedDrawings/examples/config/retarget/fair1_spf.yaml",
        output_video_path="/tmp/scene_0.mp4",
        window_dimensions=(1080, 1080),
        camera_pos=[0.0, 0.0, 3.5],
        camera_fwd=[0.0, 0.0, -1.0],
        clear_color=[1.0, 1.0, 1.0, 1.0],
        char_starting_location=[0.0, 0.0, 0.0],
        scale=1.0,
    )

    # 1. Verify yaml.safe_load
    parsed = yaml.safe_load(yaml_str)
    assert isinstance(parsed, dict), "yaml.safe_load did not return a dictionary"

    # 2. Check required top-level sections
    for required_section in ["scene", "controller", "view"]:
        assert required_section in parsed, f"Missing required section '{required_section}' in generated YAML"

    # 3. Check 'view' section contents
    view = parsed["view"]
    assert view["WINDOW_DIMENSIONS"] == [1080, 1080]
    assert view["CAMERA_POS"] == [0.0, 0.0, 3.5]
    assert view["CAMERA_FWD"] == [0.0, 0.0, -1.0]
    assert view["CLEAR_COLOR"] == [1.0, 1.0, 1.0, 1.0]

    # 4. Check 'scene' section contents
    scene = parsed["scene"]
    assert "ANIMATED_CHARACTERS" in scene
    assert isinstance(scene["ANIMATED_CHARACTERS"], list)
    assert len(scene["ANIMATED_CHARACTERS"]) == 1

    char_dict = scene["ANIMATED_CHARACTERS"][0]
    assert char_dict["character_cfg"] == "/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml"
    assert char_dict["motion_cfg"] == "/workspace/AnimatedDrawings/examples/config/motion/jumping.yaml"
    assert char_dict["retarget_cfg"] == "/workspace/AnimatedDrawings/examples/config/retarget/fair1_spf.yaml"
    assert char_dict["char_starting_location"] == [0.0, 0.0, 0.0]
    assert char_dict["scale"] == 1.0

    # 5. Check 'controller' section contents
    controller = parsed["controller"]
    assert controller["MODE"] == "video_render"
    assert controller["OUTPUT_VIDEO_PATH"] == "/tmp/scene_0.mp4"
    assert controller["OUTPUT_VIDEO_CODEC"] == "mp4v"

    print("[PASS] standard_mvc_yaml_generation_and_parsing passed successfully")


def test_simulated_server_and_handler_yaml_output():
    """Simulate exact calls from server.py and handler.py and test yaml validity."""
    # From server.py line 202
    server_yaml_str = generate_mvc_yaml(
        character_cfg="/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml",
        motion_cfg="/workspace/AnimatedDrawings/examples/config/motion/zombie.yaml",
        retarget_cfg="/workspace/AnimatedDrawings/examples/config/retarget/fair1_spf.yaml",
        output_video_path="/tmp/scene_job123_0.mp4",
        window_dimensions=(1080, 1080),
        camera_pos=[0.0, 0.0, 3.5],
        camera_fwd=[0.0, 0.0, -1.0],
        clear_color=[1.0, 1.0, 1.0, 1.0],
        char_starting_location=[0.0, 0.0, 0.0],
        scale=1.0,
    )
    server_parsed = yaml.safe_load(server_yaml_str)
    assert server_parsed["controller"]["OUTPUT_VIDEO_PATH"] == "/tmp/scene_job123_0.mp4"
    assert server_parsed["scene"]["ANIMATED_CHARACTERS"][0]["scale"] == 1.0

    # From handler.py line 130
    handler_yaml_str = generate_mvc_yaml(
        character_cfg="/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml",
        motion_cfg="/workspace/AnimatedDrawings/examples/config/motion/jesse_dance.yaml",
        retarget_cfg="/workspace/AnimatedDrawings/examples/config/retarget/mixamo_fff.yaml",
        output_video_path="/tmp/scene_0.mp4",
        window_dimensions=(1080, 1080),
        camera_pos=[0.0, 0.0, 3.5],
        camera_fwd=[0.0, 0.0, -1.0],
        clear_color=[1.0, 1.0, 1.0, 1.0],
        char_starting_location=[0.0, 0.0, 0.0],
        scale=1.0,
    )
    handler_parsed = yaml.safe_load(handler_yaml_str)
    assert handler_parsed["controller"]["OUTPUT_VIDEO_PATH"] == "/tmp/scene_0.mp4"
    assert handler_parsed["scene"]["ANIMATED_CHARACTERS"][0]["motion_cfg"] == "/workspace/AnimatedDrawings/examples/config/motion/jesse_dance.yaml"

    print("[PASS] simulated server and handler YAML output tests passed")


def test_edge_case_path_formatting_and_special_chars():
    """Stress test paths with spaces, quotes, windows paths, backslashes, and special characters."""
    special_paths = [
        "C:\\Users\\test user\\My Documents\\char_cfg.yaml",
        "/tmp/path with spaces/motion.yaml",
        "/tmp/path'with'quotes/retarget.yaml",
        "/tmp/path\"with\"doublequotes/video.mp4",
        "D:\\path\\to\\char_cfg_#123.yaml",
    ]

    for p in special_paths:
        yaml_str = generate_mvc_yaml(
            character_cfg=p,
            motion_cfg=p,
            retarget_cfg=p,
            output_video_path=p,
        )
        parsed = yaml.safe_load(yaml_str)
        char_info = parsed["scene"]["ANIMATED_CHARACTERS"][0]
        assert char_info["character_cfg"] == p, f"Path mismatch for character_cfg: expected {p}, got {char_info['character_cfg']}"
        assert parsed["controller"]["OUTPUT_VIDEO_PATH"] == p, f"Path mismatch for output_video_path: expected {p}, got {parsed['controller']['OUTPUT_VIDEO_PATH']}"

    print("[PASS] edge_case_path_formatting_and_special_chars passed")


def test_numeric_boundaries_and_extreme_parameters():
    """Stress test extreme scale values, negative starting locations, non-standard window dimensions."""
    test_cases = [
        # (scale, char_starting_location, window_dimensions, camera_pos)
        (0.001, [-999.9, -888.8, -777.7], (1, 1), [0.0, 0.0, 0.0]),
        (100.0, [1000.0, 5000.0, 10000.0], (3840, 2160), [10.5, -20.2, 30.8]),
        (1e-5, [0.0, 0.0, 0.0], (1920, 1080), [-1.0, 0.0, 1.0]),
    ]

    for scale, char_loc, win_dim, cam_pos in test_cases:
        yaml_str = generate_mvc_yaml(
            character_cfg="char.yaml",
            motion_cfg="motion.yaml",
            retarget_cfg="retarget.yaml",
            output_video_path="out.mp4",
            scale=scale,
            char_starting_location=char_loc,
            window_dimensions=win_dim,
            camera_pos=cam_pos,
        )
        parsed = yaml.safe_load(yaml_str)

        char_info = parsed["scene"]["ANIMATED_CHARACTERS"][0]
        assert pytest.approx(char_info["scale"]) == scale
        assert pytest.approx(char_info["char_starting_location"]) == char_loc
        assert parsed["view"]["WINDOW_DIMENSIONS"] == list(win_dim)
        assert pytest.approx(parsed["view"]["CAMERA_POS"]) == cam_pos

    print("[PASS] numeric_boundaries_and_extreme_parameters passed")


def test_yaml_dump_determinism_and_key_order():
    """Ensure yaml output is deterministic and maintains view, scene, controller order."""
    yaml_str1 = generate_mvc_yaml("c.yaml", "m.yaml", "r.yaml", "out.mp4")
    yaml_str2 = generate_mvc_yaml("c.yaml", "m.yaml", "r.yaml", "out.mp4")
    assert yaml_str1 == yaml_str2, "generate_mvc_yaml output is non-deterministic"

    # Verify top-level key order in string representation: view -> scene -> controller
    view_pos = yaml_str1.find("view:")
    scene_pos = yaml_str1.find("scene:")
    controller_pos = yaml_str1.find("controller:")
    assert view_pos != -1 and scene_pos != -1 and controller_pos != -1
    assert view_pos < scene_pos < controller_pos, f"Key order was not view -> scene -> controller: view={view_pos}, scene={scene_pos}, controller={controller_pos}"

    print("[PASS] yaml_dump_determinism_and_key_order passed")


if __name__ == "__main__":
    test_server_and_handler_imports_and_usage()
    test_standard_mvc_yaml_generation_and_parsing()
    test_simulated_server_and_handler_yaml_output()
    test_edge_case_path_formatting_and_special_chars()
    test_numeric_boundaries_and_extreme_parameters()
    test_yaml_dump_determinism_and_key_order()
    print("\n>>> ALL STRESS TESTS PASSED SUCCESSFULLY! <<<")
