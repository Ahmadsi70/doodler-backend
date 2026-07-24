"""
Character generation and image processing utilities for Doodler AI backend.
Provides strict prompt construction and texture image post-processing with uniform scaling and white margin padding.
"""

from PIL import Image

PREFIX_DIRECTIVE = "full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background"
SAFEGUARD_DIRECTIVE = "full body visible, head to toe, centered in frame, pure white background, no crop"


def build_strict_character_prompt(spec: dict) -> str:
    """
    Constructs an enhanced SDXL-Turbo character prompt prepending strict framing directives
    and appending negative/safeguard directives.
    
    Framing directives prepended:
        "full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background"
        
    Safeguard directives appended:
        "full body visible, head to toe, centered in frame, pure white background, no crop"
    """
    part_prompts = []
    if isinstance(spec, dict):
        parts = spec.get("sketch", {}).get("parts", [])
        for p in parts:
            if isinstance(p, dict) and p.get("prompt"):
                prompt_text = str(p.get("prompt")).strip(" .,")
                if prompt_text:
                    part_prompts.append(prompt_text)
                    
        if not part_prompts:
            if spec.get("character_prompt"):
                part_prompts.append(str(spec["character_prompt"]).strip(" .,"))
            elif spec.get("prompt"):
                part_prompts.append(str(spec["prompt"]).strip(" .,"))
            elif spec.get("brief", {}).get("user_prompt"):
                part_prompts.append(str(spec["brief"]["user_prompt"]).strip(" .,"))

    middle = ", ".join(part_prompts) if part_prompts else "character design"
    
    return f"{PREFIX_DIRECTIVE}, {middle}, {SAFEGUARD_DIRECTIVE}"


def process_character_texture(
    img_no_bg: Image.Image,
    target_size: tuple[int, int] = (512, 512),
    margin: int = 30,
) -> Image.Image:
    """
    Processes character texture image after background removal (`rembg`):
    1. Converts image to RGBA mode if needed.
    2. Crops character to its alpha channel bounding box.
    3. Uniformly scales character to fit within `target_size` preserving aspect ratio
       while leaving a distinct white padding `margin` on all 4 edges (top, bottom, left, right).
    4. Pastes centered character onto a pure white (255, 255, 255) RGB canvas.
    """
    if img_no_bg.mode != "RGBA":
        img_no_bg = img_no_bg.convert("RGBA")
        
    alpha = img_no_bg.getchannel("A")
    bbox = alpha.getbbox()
    
    target_w, target_h = target_size
    canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
    
    if not bbox:
        return canvas
        
    cropped = img_no_bg.crop(bbox)
    crop_w, crop_h = cropped.size
    if crop_w == 0 or crop_h == 0:
        return canvas
        
    max_w = max(1, target_w - 2 * margin)
    max_h = max(1, target_h - 2 * margin)
    
    scale = min(max_w / crop_w, max_h / crop_h)
    new_w = max(1, int(round(crop_w * scale)))
    new_h = max(1, int(round(crop_h * scale)))
    
    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    scaled = cropped.resize((new_w, new_h), resample_filter)
    
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    
    canvas.paste(scaled, (offset_x, offset_y), mask=scaled.getchannel("A"))
    return canvas


def build_mvc_yaml_dict(
    character_cfg: str,
    motion_cfg: str,
    retarget_cfg: str,
    output_video_path: str,
    window_dimensions: tuple[int, int] | list[int] | None = None,
    camera_pos: list[float] | None = None,
    camera_fwd: list[float] | None = None,
    clear_color: list[float] | None = None,
    char_starting_location: list[float] | None = None,
    scale: float = 1.0,
    output_video_codec: str = "mp4v",
    mode: str = "video_render",
) -> dict:
    """
    Builds the dictionary structure for AnimatedDrawings MVC (Model-View-Controller) YAML configuration.
    Injects explicit framing, camera vectors (CAMERA_POS, CAMERA_FWD), non-default resolution (WINDOW_DIMENSIONS),
    clear background color (CLEAR_COLOR), character starting location (char_starting_location), and character scale.
    """
    if window_dimensions is None:
        window_dimensions = [1080, 1080]
    if camera_pos is None:
        camera_pos = [0.0, 0.0, 3.5]
    if camera_fwd is None:
        camera_fwd = [0.0, 0.0, -1.0]
    if clear_color is None:
        clear_color = [1.0, 1.0, 1.0, 1.0]
    if char_starting_location is None:
        char_starting_location = [0.0, 0.0, 0.0]

    return {
        "view": {
            "WINDOW_DIMENSIONS": list(window_dimensions),
            "CAMERA_POS": list(camera_pos),
            "CAMERA_FWD": list(camera_fwd),
            "CLEAR_COLOR": list(clear_color),
        },
        "scene": {
            "ANIMATED_CHARACTERS": [
                {
                    "character_cfg": character_cfg,
                    "motion_cfg": motion_cfg,
                    "retarget_cfg": retarget_cfg,
                    "char_starting_location": list(char_starting_location),
                    "scale": float(scale),
                }
            ]
        },
        "controller": {
            "MODE": mode,
            "OUTPUT_VIDEO_PATH": output_video_path,
            "OUTPUT_VIDEO_CODEC": output_video_codec,
        },
    }


def generate_mvc_yaml(
    character_cfg: str,
    motion_cfg: str,
    retarget_cfg: str,
    output_video_path: str,
    **kwargs,
) -> str:
    """
    Generates a formatted YAML string representation of the MVC configuration.
    """
    import yaml
    cfg_dict = build_mvc_yaml_dict(
        character_cfg=character_cfg,
        motion_cfg=motion_cfg,
        retarget_cfg=retarget_cfg,
        output_video_path=output_video_path,
        **kwargs,
    )
    return yaml.dump(cfg_dict, sort_keys=False)

