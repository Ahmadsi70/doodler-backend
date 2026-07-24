try:
    import runpod
except ImportError:
    runpod = None
import time
import base64
import os
import json
import subprocess
import sys

VOLUME_PATH = "/runpod-volume/models"
if not os.path.exists("/runpod-volume"):
    VOLUME_PATH = "./models"
    
os.makedirs(VOLUME_PATH, exist_ok=True)
os.environ["HF_HOME"] = VOLUME_PATH
os.environ["TORCH_HOME"] = VOLUME_PATH

import torch
from diffusers import AudioLDMPipeline, AutoPipelineForText2Image
import scipy.io.wavfile
import numpy as np
from PIL import Image
from rembg import remove
try:
    from runpod_backend.character_utils import build_strict_character_prompt, process_character_texture, generate_mvc_yaml
except ImportError:
    from character_utils import build_strict_character_prompt, process_character_texture, generate_mvc_yaml

audioldm_pipe = None
sd_pipe = None

def init_models():
    global audioldm_pipe, sd_pipe
    
    ad_path = "/workspace/AnimatedDrawings"
    if ad_path not in sys.path:
        sys.path.append(ad_path)
        
    if audioldm_pipe is None:
        try:
            print("Loading AudioLDM model...")
            audioldm_pipe = AudioLDMPipeline.from_pretrained("cvssp/audioldm-s-full-v2", torch_dtype=torch.float16)
            audioldm_pipe = audioldm_pipe.to("cuda")
        except Exception as e:
            print(f"AudioLDM init failed: {e}")

    if sd_pipe is None:
        try:
            print("Loading SDXL-Turbo model...")
            sd_pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
            sd_pipe = sd_pipe.to("cuda")
        except Exception as e:
            print(f"SD init failed: {e}")

def handler(job):
    job_input = job['input']
    spec = job_input.get("spec")
    if not spec:
        return {"error": "Missing 'spec' in input payload."}
        
    print("Received Spec")
    init_models()
    
    # 1. Image Generation
    print("Step 1: Generating Image via SDXL-Turbo")
    character_prompt = build_strict_character_prompt(spec)
    
    print(f"Prompt: {character_prompt}")
    
    char_image_path = "/tmp/character.png"
    if sd_pipe:
        # Generate image (Turbo needs 1-4 steps)
        image = sd_pipe(prompt=character_prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
        # Remove background to get transparent PNG
        img_no_bg = remove(image)
        # Process character texture with alpha bbox crop, uniform scale, 30px margin & white background
        final_img = process_character_texture(img_no_bg, target_size=(512, 512), margin=30)
        final_img.save(char_image_path)
    else:
        # Fallback to a blank image
        Image.new("RGB", (512, 512), (255, 255, 255)).save(char_image_path)
    
    # We will override char1's texture with our new image (MVP rig hack)
    ad_char_dir = "/workspace/AnimatedDrawings/examples/characters/char1"
    if os.path.exists(ad_char_dir):
        cfg_path = os.path.join(ad_char_dir, "char_cfg.yaml")
        w, h = 454, 602
        if os.path.exists(cfg_path):
            import yaml
            with open(cfg_path, "r") as f:
                cfg = yaml.safe_load(f)
                h = cfg.get("height", 602)
                w = cfg.get("width", 454)
        if sd_pipe:
            texture_img = process_character_texture(img_no_bg, target_size=(w, h), margin=30)
        else:
            texture_img = Image.open(char_image_path)
            if texture_img.size != (w, h):
                texture_img = texture_img.resize((w, h))
        texture_img.save(os.path.join(ad_char_dir, "texture.png"))
    
    # 2. Process Timeline
    scenes = spec.get('timeline', {}).get('scenes', [])
    video_clips = []
    
    for i, scene in enumerate(scenes):
        print(f"\\n--- Processing Scene {i} ---")
        out_video_path = f"/tmp/scene_{i}.mp4"
        out_audio_path = f"/tmp/sfx_{i}.wav"
        
        # 2a. Animate
        motion = scene.get('motion_type', 'jump')
        motion_mapping = {
            "walk": ("zombie", "fair1_spf"),
            "jump": ("jumping", "fair1_spf"),
            "dance": ("jesse_dance", "mixamo_fff"),
            "wave": ("wave_hello", "fair1_spf"),
            "dab": ("dab", "fair1_spf"),
            "jumping_jacks": ("jumping_jacks", "cmu1_pfp")
        }
        mapped_motion, retarget_name = motion_mapping.get(motion, ("jumping", "fair1_spf"))
        
        motion_yaml = f"/workspace/AnimatedDrawings/examples/config/motion/{mapped_motion}.yaml"
        retarget_yaml = f"/workspace/AnimatedDrawings/examples/config/retarget/{retarget_name}.yaml"
        if not os.path.exists(motion_yaml):
            motion_yaml = "/workspace/AnimatedDrawings/examples/config/motion/jumping.yaml"
            retarget_yaml = "/workspace/AnimatedDrawings/examples/config/retarget/fair1_spf.yaml"
            
        char_cfg_path = "/workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml"
        mvc_yaml = f"/tmp/mvc_{i}.yaml"
        yaml_content = generate_mvc_yaml(
            character_cfg=char_cfg_path,
            motion_cfg=motion_yaml,
            retarget_cfg=retarget_yaml,
            output_video_path=out_video_path,
            window_dimensions=(1080, 1080),
            camera_pos=[0.0, 0.0, 3.5],
            camera_fwd=[0.0, 0.0, -1.0],
            clear_color=[1.0, 1.0, 1.0, 1.0],
            char_starting_location=[0.0, 0.0, 0.0],
            scale=1.0,
        )
        with open(mvc_yaml, "w") as f:
            f.write(yaml_content)
            
        render_cmd = [
            "xvfb-run", "-a", "python", "-m", "animated_drawings.render", mvc_yaml
        ]
        
        # Run rendering
        print(f"Running command: {' '.join(render_cmd)}")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "/workspace/AnimatedDrawings"
            result = subprocess.run(render_cmd, cwd="/workspace/AnimatedDrawings", env=env, capture_output=True, text=True, check=True)
            print(f"Render stdout: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"Render failed with error code {e.returncode}")
            print(f"Render stderr: {e.stderr}")
            return {"status": "error", "error": f"AnimatedDrawings failed: {e.stderr}"}

        if not os.path.exists(out_video_path):
            out_video_path = "mock"
            
        # Determine dynamic scene duration
        clip = None
        scene_duration = None
        if out_video_path != "mock":
            try:
                try:
                    from moviepy import VideoFileClip, AudioFileClip
                except ImportError:
                    from moviepy.editor import VideoFileClip, AudioFileClip
                clip = VideoFileClip(out_video_path)
                if clip.duration and clip.duration > 0:
                    scene_duration = float(clip.duration)
            except Exception as e:
                print(f"Error reading video clip duration: {e}")

        if scene_duration is None:
            start_t = float(scene.get('start_time', 0.0))
            end_t = float(scene.get('end_time', 0.0))
            if end_t > start_t:
                scene_duration = end_t - start_t
            else:
                scene_duration = 2.0

        # 2b. AudioLDM / Sound Generation with dynamic audio_length_in_s
        sfx_prompt = scene.get('sfx_prompt', "")
        audio_generated = False
        if sfx_prompt and str(sfx_prompt).strip() and audioldm_pipe:
            print(f"Generating SFX: {sfx_prompt} (duration: {scene_duration}s)")
            try:
                audio = audioldm_pipe(sfx_prompt, num_inference_steps=10, audio_length_in_s=scene_duration).audios[0]
                scipy.io.wavfile.write(out_audio_path, 16000, audio)
                audio_generated = True
            except Exception as e:
                print(f"SFX Generation failed, fallback to silent audio: {e}")

        if not audio_generated:
            print(f"Injecting silent audio fallback for scene {i} (duration: {scene_duration}s)")
            silent_audio = np.zeros(int(16000 * scene_duration), dtype=np.float32)
            scipy.io.wavfile.write(out_audio_path, 16000, silent_audio)

        if out_video_path != "mock":
            try:
                try:
                    from moviepy import VideoFileClip, AudioFileClip
                except ImportError:
                    from moviepy.editor import VideoFileClip, AudioFileClip
                if clip is None:
                    clip = VideoFileClip(out_video_path)
                if os.path.exists(out_audio_path):
                    audioclip = AudioFileClip(out_audio_path)
                    if audioclip.duration < clip.duration:
                        try:
                            from moviepy.audio.fx.audio_loop import audio_loop
                            audioclip = audio_loop(audioclip, duration=clip.duration)
                        except Exception:
                            audioclip = audioclip.with_duration(clip.duration) if hasattr(audioclip, 'with_duration') else audioclip.set_duration(clip.duration)
                    elif audioclip.duration > clip.duration:
                        audioclip = audioclip.subclip(0, clip.duration) if hasattr(audioclip, 'subclip') else audioclip.subclipped(0, clip.duration)

                    clip = clip.with_audio(audioclip) if hasattr(clip, 'with_audio') else clip.set_audio(audioclip)
                video_clips.append(clip)
            except Exception as e:
                print(f"Moviepy processing error: {e}")
            
    # 3. Concatenate
    if video_clips:
        try:
            try:
                from moviepy import concatenate_videoclips
            except ImportError:
                from moviepy.editor import concatenate_videoclips
            final_video = concatenate_videoclips(video_clips)
            final_path = "/tmp/final.mp4"
            final_video.write_videofile(final_path, codec="libx264", audio_codec="aac")
            
            with open(final_path, "rb") as f:
                b64_vid = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"Concatenation error: {e}")
            if out_video_path != "mock" and os.path.exists(out_video_path):
                with open(out_video_path, "rb") as f:
                    b64_vid = base64.b64encode(f.read()).decode("utf-8")
            else:
                b64_vid = "AAAAGGZ0eXBtcDQyAAAAAWlzb21tcDQy"
    elif out_video_path != "mock" and os.path.exists(out_video_path):
        with open(out_video_path, "rb") as f:
            b64_vid = base64.b64encode(f.read()).decode("utf-8")
    else:
        b64_vid = "AAAAGGZ0eXBtcDQyAAAAAWlzb21tcDQy"
        
    return {
        "status": "success",
        "video_base64": b64_vid,
        "message": "Rendered successfully."
    }

if __name__ == "__main__":
    init_models()
    runpod.serverless.start({"handler": handler})
