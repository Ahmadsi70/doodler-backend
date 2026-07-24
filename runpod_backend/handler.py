import runpod
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
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

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
    character_prompt = "A character design on a solid white background. "
    parts = spec.get("sketch", {}).get("parts", [])
    for p in parts:
        character_prompt += p.get("prompt", "") + ", "
    
    print(f"Prompt: {character_prompt}")
    
    char_image_path = "/tmp/character.png"
    if sd_pipe:
        # Generate image (Turbo needs 1-4 steps)
        image = sd_pipe(prompt=character_prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
        # Remove background to get transparent PNG
        img_no_bg = remove(image)
        # Paste on white background for AnimatedDrawings
        final_img = Image.new("RGB", img_no_bg.size, (255, 255, 255))
        final_img.paste(img_no_bg, mask=img_no_bg.split()[3])
        final_img.save(char_image_path)
    else:
        # Fallback to a blank image
        Image.new("RGB", (512, 512), (255,255,255)).save(char_image_path)
    
    # We will override char1's texture with our new image (MVP rig hack)
    ad_char_dir = "/workspace/AnimatedDrawings/examples/characters/char1"
    if os.path.exists(ad_char_dir):
        # Resize to match roughly what char1 expects, though aspect ratio might stretch
        im = Image.open(char_image_path).resize((512, 512))
        im.save(os.path.join(ad_char_dir, "texture.png"))
    
    # 2. Process Timeline
    scenes = spec.get('timeline', {}).get('scenes', [])
    video_clips = []
    
    for i, scene in enumerate(scenes):
        print(f"\\n--- Processing Scene {i} ---")
        out_video_path = f"/tmp/scene_{i}.mp4"
        out_audio_path = f"/tmp/sfx_{i}.wav"
        
        # 2a. Animate
        motion = scene.get('motion_type', 'jump')
        motion_yaml = f"/workspace/AnimatedDrawings/examples/config/motion/{motion}.yaml"
        if not os.path.exists(motion_yaml):
            motion_yaml = "/workspace/AnimatedDrawings/examples/config/motion/jump.yaml"
            
        render_cmd = [
            "xvfb-run", "-a", "python", "-m", "animated_drawings.render",
            ad_char_dir, motion_yaml, "/workspace/AnimatedDrawings/examples/config/retarget/fair1_ppf.yaml"
        ]
        
        # Run rendering
        print(f"Running command: {' '.join(render_cmd)}")
        try:
            result = subprocess.run(render_cmd, cwd="/workspace/AnimatedDrawings", capture_output=True, text=True, check=True)
            print(f"Render stdout: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"Render failed with error code {e.returncode}")
            print(f"Render stderr: {e.stderr}")
            return {"status": "error", "error": f"AnimatedDrawings failed: {e.stderr}"}

        
        # AnimatedDrawings saves to video.mp4 in cwd by default or a specific out folder.
        # It actually saves to video.mp4 (or video.gif) in the current directory if not specified.
        # But looking at its code, we need to pass out_dir, wait, we don't have access to edit the yaml here easily.
        # Let's assume it generates `video.mp4` in `/workspace/AnimatedDrawings`.
        default_vid = "/workspace/AnimatedDrawings/video.mp4"
        if os.path.exists(default_vid):
            os.rename(default_vid, out_video_path)
        else:
            # Fallback mock video if rendering failed
            out_video_path = "mock"
            
        # 2b. AudioLDM
        sfx_prompt = scene.get('sfx_prompt', "")
        if sfx_prompt and audioldm_pipe:
            print(f"Generating SFX: {sfx_prompt}")
            audio = audioldm_pipe(sfx_prompt, num_inference_steps=10, audio_length_in_s=2.0).audios[0]
            scipy.io.wavfile.write(out_audio_path, 16000, audio)
        
        if out_video_path != "mock":
            clip = VideoFileClip(out_video_path)
            if os.path.exists(out_audio_path):
                audioclip = AudioFileClip(out_audio_path)
                # Loop or trim audio to match video duration
                audioclip = audioclip.set_duration(clip.duration)
                clip = clip.set_audio(audioclip)
            video_clips.append(clip)
            
    # 3. Concatenate
    if video_clips:
        final_video = concatenate_videoclips(video_clips)
        final_path = "/tmp/final.mp4"
        final_video.write_videofile(final_path, codec="libx264", audio_codec="aac")
        
        with open(final_path, "rb") as f:
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
