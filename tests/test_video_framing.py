"""
Programmatic Verification Script for AnimatedDrawings Output Configurations (mvc_yaml).
Verifies that character framing, camera position, window dimensions, clear color, starting location,
and scale are explicitly configured and adjusted from fallback defaults to center the character.
"""

import sys
import os
from pathlib import Path
import yaml
import pytest

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from runpod_backend.character_utils import build_mvc_yaml_dict, generate_mvc_yaml
except ImportError:
    from character_utils import build_mvc_yaml_dict, generate_mvc_yaml


def test_build_mvc_yaml_dict_defaults():
    """
    Verifies build_mvc_yaml_dict returns expected view, scene, controller configurations
    with non-default window dimensions (1080x1080), explicit camera position, forward vector,
    clear color, character starting location, and scale.
    """
    cfg = build_mvc_yaml_dict(
        character_cfg="/path/to/char_cfg.yaml",
        motion_cfg="/path/to/motion.yaml",
        retarget_cfg="/path/to/retarget.yaml",
        output_video_path="/tmp/output_video.mp4",
    )

    # 1. View section assertion
    assert "view" in cfg, "mvc_yaml config missing 'view' section"
    view = cfg["view"]
    assert view["WINDOW_DIMENSIONS"] == [1080, 1080], f"WINDOW_DIMENSIONS fallback default not overridden, got {view['WINDOW_DIMENSIONS']}"
    assert view["CAMERA_POS"] == [0.0, 0.0, 3.5], f"CAMERA_POS not explicitly configured, got {view['CAMERA_POS']}"
    assert view["CAMERA_FWD"] == [0.0, 0.0, -1.0], f"CAMERA_FWD not explicitly configured, got {view['CAMERA_FWD']}"
    assert view["CLEAR_COLOR"] == [1.0, 1.0, 1.0, 1.0], f"CLEAR_COLOR not explicitly configured, got {view['CLEAR_COLOR']}"

    # 2. Scene section assertion
    assert "scene" in cfg, "mvc_yaml config missing 'scene' section"
    scene = cfg["scene"]
    assert "ANIMATED_CHARACTERS" in scene and len(scene["ANIMATED_CHARACTERS"]) > 0
    char_info = scene["ANIMATED_CHARACTERS"][0]
    assert char_info["character_cfg"] == "/path/to/char_cfg.yaml"
    assert char_info["motion_cfg"] == "/path/to/motion.yaml"
    assert char_info["retarget_cfg"] == "/path/to/retarget.yaml"
    assert char_info["char_starting_location"] == [0.0, 0.0, 0.0], f"char_starting_location not centered, got {char_info['char_starting_location']}"
    assert char_info["scale"] == 1.0, f"scale not explicitly configured, got {char_info['scale']}"

    # 3. Controller section assertion
    assert "controller" in cfg, "mvc_yaml config missing 'controller' section"
    controller = cfg["controller"]
    assert controller["MODE"] == "video_render"
    assert controller["OUTPUT_VIDEO_PATH"] == "/tmp/output_video.mp4"
    assert controller["OUTPUT_VIDEO_CODEC"] == "mp4v"


def test_build_mvc_yaml_dict_non_mutable_defaults():
    """
    Verifies build_mvc_yaml_dict uses None for defaults in signature and instantiates new lists per call.
    """
    import inspect
    sig = inspect.signature(build_mvc_yaml_dict)
    assert sig.parameters["window_dimensions"].default is None
    assert sig.parameters["camera_pos"].default is None
    assert sig.parameters["camera_fwd"].default is None
    assert sig.parameters["clear_color"].default is None
    assert sig.parameters["char_starting_location"].default is None

    cfg1 = build_mvc_yaml_dict("c.yaml", "m.yaml", "r.yaml", "o1.mp4")
    cfg2 = build_mvc_yaml_dict("c.yaml", "m.yaml", "r.yaml", "o2.mp4")

    # Verify that returned lists are distinct object instances
    assert cfg1["view"]["CAMERA_POS"] is not cfg2["view"]["CAMERA_POS"]
    assert cfg1["view"]["WINDOW_DIMENSIONS"] is not cfg2["view"]["WINDOW_DIMENSIONS"]


def test_generate_mvc_yaml_string_parsing():
    """
    Verifies that generate_mvc_yaml produces a valid YAML string that parses
    back into a dict matching all framing requirements.
    """
    yaml_str = generate_mvc_yaml(
        character_cfg="/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml",
        motion_cfg="/workspace/AnimatedDrawings/examples/config/motion/jumping.yaml",
        retarget_cfg="/workspace/AnimatedDrawings/examples/config/retarget/fair1_spf.yaml",
        output_video_path="/tmp/scene_test.mp4",
        window_dimensions=(1080, 1080),
        camera_pos=[0.0, 0.0, 3.5],
        camera_fwd=[0.0, 0.0, -1.0],
        clear_color=[1.0, 1.0, 1.0, 1.0],
        char_starting_location=[0.0, 0.0, 0.0],
        scale=1.0,
    )

    parsed = yaml.safe_load(yaml_str)

    # Verify root sections
    assert "view" in parsed
    assert "scene" in parsed
    assert "controller" in parsed

    # Verify framing and view parameters
    assert parsed["view"]["WINDOW_DIMENSIONS"] == [1080, 1080]
    assert parsed["view"]["CAMERA_POS"] == [0.0, 0.0, 3.5]
    assert parsed["view"]["CAMERA_FWD"] == [0.0, 0.0, -1.0]
    assert parsed["view"]["CLEAR_COLOR"] == [1.0, 1.0, 1.0, 1.0]

    # Verify character position and scale parameters
    anim_char = parsed["scene"]["ANIMATED_CHARACTERS"][0]
    assert anim_char["char_starting_location"] == [0.0, 0.0, 0.0]
    assert anim_char["scale"] == 1.0


def test_custom_framing_parameters():
    """
    Verifies that custom framing overrides (e.g. widescreen, custom camera position, custom scale)
    are respected by build_mvc_yaml_dict and generate_mvc_yaml.
    """
    cfg = build_mvc_yaml_dict(
        character_cfg="/path/char.yaml",
        motion_cfg="/path/motion.yaml",
        retarget_cfg="/path/retarget.yaml",
        output_video_path="/tmp/custom.mp4",
        window_dimensions=(1920, 1080),
        camera_pos=[0.0, 0.5, 4.0],
        camera_fwd=[0.0, -0.1, -1.0],
        clear_color=[0.9, 0.9, 0.9, 1.0],
        char_starting_location=[0.1, -0.05, 0.0],
        scale=1.25,
    )

    assert cfg["view"]["WINDOW_DIMENSIONS"] == [1920, 1080]
    assert cfg["view"]["CAMERA_POS"] == [0.0, 0.5, 4.0]
    assert cfg["view"]["CAMERA_FWD"] == [0.0, -0.1, -1.0]
    assert cfg["view"]["CLEAR_COLOR"] == [0.9, 0.9, 0.9, 1.0]
    assert cfg["scene"]["ANIMATED_CHARACTERS"][0]["char_starting_location"] == [0.1, -0.05, 0.0]
    assert cfg["scene"]["ANIMATED_CHARACTERS"][0]["scale"] == 1.25


def test_ad_config_scene_config_override_logic(tmp_path):
    """
    Verifies that ad_config.SceneConfig correctly applies char_starting_location and scale
    overrides when loaded via mvc_yaml structure.
    """
    try:
        from ad_config import SceneConfig, RetargetConfig, MotionConfig, CharacterConfig
    except ImportError:
        pytest.skip("ad_config or AnimatedDrawings dependencies not installed in test environment")

    # Create dummy character, motion, and retarget yaml files for SceneConfig initialization
    char_cfg_file = tmp_path / "char_cfg.yaml"
    char_cfg_file.write_text("""
height: 600
width: 400
skeleton:
  - loc: [200, 300]
    name: root
    parent: null
""", encoding="utf-8")
    (tmp_path / "texture.png").write_bytes(b"dummy_png")
    (tmp_path / "mask.png").write_bytes(b"dummy_png")

    motion_cfg_file = tmp_path / "motion.yaml"
    bvh_file = tmp_path / "dummy.bvh"
    bvh_file.write_text("HIERARCHY\nROOT root\n{\nOFFSET 0 0 0\nCHANNELS 3 Xposition Yposition Zposition\n}\nMOTION\nFrames: 1\nFrame Time: 0.033\n0 0 0", encoding="utf-8")
    
    motion_cfg_file.write_text(f"""
filepath: {bvh_file}
groundplane_joint: root
forward_perp_joint_vectors:
  - [root, root]
scale: 0.5
up: "+y"
""", encoding="utf-8")

    retarget_cfg_file = tmp_path / "retarget.yaml"
    retarget_cfg_file.write_text("""
char_starting_location: [1.0, 1.0, 1.0]
bvh_projection_bodypart_groups:
  - name: body
    method: pca
    bvh_joint_names: [root]
char_bodypart_groups:
  - bvh_depth_drivers: [root]
    char_joints: [root]
char_bvh_root_offset:
  bvh_projection_bodypart_group_for_offset: body
  bvh_joints: [[root]]
  char_joints: [[root]]
char_joint_bvh_joints_mapping:
  root: [root, root]
char_runtime_checks: []
""", encoding="utf-8")

    scene_cfg = {
        "ADD_FLOOR": False,
        "ADD_AD_RETARGET_BVH": False,
        "ANIMATED_CHARACTERS": [
            {
                "character_cfg": str(char_cfg_file),
                "motion_cfg": str(motion_cfg_file),
                "retarget_cfg": str(retarget_cfg_file),
                "char_starting_location": [0.0, 0.0, 0.0],
                "scale": 1.0,
            }
        ]
    }

    sc = SceneConfig(scene_cfg)
    char_cfg_obj, retarget_cfg_obj, motion_cfg_obj = sc.animated_characters[0]

    assert retarget_cfg_obj.char_start_loc == [0.0, 0.0, 0.0], "RetargetConfig char_start_loc was not overridden by mvc_yaml scene entry"
    assert motion_cfg_obj.scale == 1.0, "MotionConfig scale was not overridden by mvc_yaml scene entry"


def test_handler_video_render_path_and_env():
    """
    Verifies runpod_backend/handler.py checks out_video_path directly and sets PYTHONPATH in subprocess env.
    """
    handler_path = WORKSPACE_ROOT / "runpod_backend" / "handler.py"
    content = handler_path.read_text(encoding="utf-8")

    assert 'env["PYTHONPATH"] = "/workspace/AnimatedDrawings"' in content, "handler.py missing PYTHONPATH set in env"
    assert 'subprocess.run(render_cmd, cwd="/workspace/AnimatedDrawings", env=env' in content, "handler.py subprocess.run does not pass env"
    assert 'if not os.path.exists(out_video_path):' in content, "handler.py does not check out_video_path directly"
    assert 'default_vid = "/workspace/AnimatedDrawings/video.mp4"' not in content, "handler.py still contains stale default_vid check"
