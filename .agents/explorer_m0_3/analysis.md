# AnimatedDrawings & AudioLDM Pipeline Technical Analysis

## Executive Summary
This document presents a comprehensive analysis of the 2D animation rendering pipeline (**AnimatedDrawings**) and the audio generation/multiplexing pipeline (**AudioLDM**) in the Doodler AI project (`c:\Users\badri\Story`).

Key findings include:
1. **AnimatedDrawings Framing & Centering**: The current backend (`runpod_backend/server.py` and `runpod_backend/handler.py`) generates a minimal `mvc_yaml` configuration that entirely omits the `view:` block. This causes AnimatedDrawings to fall back to default window resolutions, unoptimized camera positions, and default retarget start locations (`char_starting_location`), leading to off-center or improperly scaled characters.
2. **AudioLDM Duration Mismatch & Truncation**: Sound effect generation hardcodes `audio_length_in_s=2.0` regardless of the actual animation scene duration (e.g. 5.0 seconds). Furthermore, MoviePy stitching uses `set_duration` (which pads with silence) or `audio_loop` (which creates repetitive sound artifacts). Missing audio tracks on silent scenes also cause concatenation anomalies.

---

## 1. AnimatedDrawings Pipeline Exploration & Framing Analysis

### 1.1 Architecture & Configuration Structure
AnimatedDrawings uses a hierarchical configuration system parsed by `ad_config.py` (`Config` class):

```
Config (mvc_yaml)
├── ViewConfig (view:)
│   ├── WINDOW_DIMENSIONS: tuple[int, int]   (e.g., [1080, 1080])
│   ├── CAMERA_POS: list[float]              (3D position [x, y, z])
│   ├── CAMERA_FWD: list[float]              (3D forward look vector [x, y, z])
│   ├── CLEAR_COLOR: list[float]             (RGBA background, e.g., [1.0, 1.0, 1.0, 1.0])
│   ├── BACKGROUND_IMAGE: str | None         (Optional background image path)
│   └── USE_MESA: bool                       (Headless rendering flag)
├── SceneConfig (scene:)
│   ├── ADD_FLOOR: bool
│   ├── ADD_AD_RETARGET_BVH: bool
│   └── ANIMATED_CHARACTERS: list[dict]
│       ├── character_cfg: str               (path to char_cfg.yaml)
│       ├── motion_cfg: str                  (path to motion.yaml)
│       └── retarget_cfg: str                (path to retarget.yaml)
└── ControllerConfig (controller:)
    ├── MODE: str                            ('video_render' or 'interactive')
    ├── OUTPUT_VIDEO_PATH: str               (path to output video file .mp4)
    └── OUTPUT_VIDEO_CODEC: str              (video codec, e.g., 'mp4v' or 'libx264')
```

Sub-configs loaded per character and scene:
- **CharacterConfig (`char_cfg.yaml`)**: Contains `width`, `height`, `skeleton` joint locations `[x, y]`, and references to `texture.png` and `mask.png`. Joint locations are normalized using `img_dim = max(height, width)`.
- **RetargetConfig (`retarget.yaml`)**: Contains `char_starting_location` (`[x, y, z]`), body part groups, joint mappings, and root offset calculations.
- **MotionConfig (`motion.yaml`)**: Contains BVH file path `filepath`, motion scale multiplier `scale`, frame index bounds (`start_frame_idx`, `end_frame_idx`), groundplane joint, and up axis.

### 1.2 Current Backend Configuration Gaps
In `runpod_backend/server.py` (lines 195-206):
```python
mvc_yaml = f"/tmp/mvc_{job_id}_{i}.yaml"
with open(mvc_yaml, "w") as f:
    f.write(f'''scene:
  ANIMATED_CHARACTERS:
    - character_cfg: /workspace/AnimatedDrawings/examples/characters/char1/char_cfg.yaml
      motion_cfg: {motion_yaml}
      retarget_cfg: {retarget_yaml}
controller:
  MODE: video_render
  OUTPUT_VIDEO_PATH: {out_video_path}
  OUTPUT_VIDEO_CODEC: mp4v
''')
```

**Issues Identified**:
1. **Omitted `view` Block**: Defaults to `mvc_base_cfg.yaml` values, which results in standard resolution (512x512), unaligned camera position `CAMERA_POS`, and default background handling.
2. **Unadjusted Retarget Position**: Uses default `retarget.yaml` without explicit `char_starting_location`, so characters may start off-center depending on BVH root offsets.
3. **Unadjusted Motion Scale**: Uses default `scale` in motion files without scaling compensation for padded or resized character textures.

### 1.3 How to Explicitly Center the Character & Upgrade Resolution
To ensure professional presentation and perfect character centering:
1. **Include explicit `view` block in `mvc_yaml`**:
   ```yaml
   view:
     WINDOW_DIMENSIONS: [1080, 1080]
     CAMERA_POS: [0.0, 0.0, 3.5]
     CAMERA_FWD: [0.0, 0.0, -1.0]
     CLEAR_COLOR: [1.0, 1.0, 1.0, 1.0]
   ```
2. **Set explicit `char_starting_location` in Retarget Config**:
   Specify `char_starting_location: [0.0, 0.0, 0.0]` (or slightly offset Y `[0.0, -0.15, 0.0]` to accommodate ground plane) so the character's bounding box centers at `(0, 0)`.
3. **Set explicit `scale` in Motion Config**:
   Tune `scale` (e.g., `0.85` - `1.0`) so character motion stays within the viewport frustum without clipping top or bottom boundaries.

---

## 2. AudioLDM Pipeline & Audio/Video Multiplexing Analysis

### 2.1 Code Location & Current Implementation
Sound effect generation and multiplexing are implemented in:
- `runpod_backend/server.py` (lines 230-252)
- `runpod_backend/handler.py` (lines 132-146)

```python
# Current AudioLDM invocation
audio = audioldm_pipe(
    sfx_prompt,
    num_inference_steps=10,
    audio_length_in_s=2.0,
    generator=torch.Generator("cuda").manual_seed(42)
).audios[0]

# Current MoviePy multiplexing
clip = VideoFileClip(out_video_path)
if os.path.exists(out_audio_path):
    from moviepy.audio.fx.audio_loop import audio_loop
    audio_clip = AudioFileClip(out_audio_path)
    audio_clip = audio_loop(audio_clip, duration=clip.duration)
    clip = clip.set_audio(audio_clip)
```

### 2.2 Root Causes of Audio Truncation and Length Mismatch
1. **Hardcoded `audio_length_in_s=2.0`**: AudioLDM is called with `audio_length_in_s=2.0` regardless of scene duration. When a scene is 5.0 seconds long, only 2 seconds of audio are generated.
2. **Flawed Truncation / Stretching Handling in MoviePy**:
   - `audioclip.set_duration(clip.duration)` in `handler.py` truncates clips longer than target, but pads clips shorter than target with dead silence. This causes sound effects to abruptly stop at 2.0s in a 5.0s video.
   - `audio_loop(audio_clip, duration=clip.duration)` in `server.py` repeatedly loops short sound effects, causing unnatural audio repetition artifacts.
3. **Multiplexing / Concatenation Failures**:
   - If `sfx_prompt` is empty for a scene, no audio file is created (`out_audio_path` missing). When `VideoFileClip` with no audio track is concatenated with clips that have audio tracks, MoviePy `concatenate_videoclips` drops audio or fails during final MP4 encoding.

### 2.3 Solution for Seamless Audio Length Matching
1. **Dynamic Duration Calculation**:
   Calculate exact scene duration prior to calling AudioLDM, either from scene spec `scene_duration = max(1.0, scene['end_time'] - scene['start_time'])` or directly after rendering video clip `scene_duration = clip.duration`.
2. **Dynamic AudioLDM Generation**:
   Pass dynamic `audio_length_in_s = float(scene_duration)` to `audioldm_pipe`. AudioLDM natively supports generating audio matching exact requested duration.
3. **Robust Audio Multiplexing & Silence Fallback**:
   - If `sfx_prompt` is provided, generate audio with `audio_length_in_s = scene_duration`.
   - If `sfx_prompt` is absent or empty, generate a silent audio track (`AudioClip(lambda t: 0, duration=clip.duration)` or a silent WAV file) to ensure every clip has a valid audio track before calling `concatenate_videoclips`.
   - Ensure clean volume fading / trimming (`audio_clip.subclip(0, clip.duration)`) to prevent pops or clicks at scene boundaries.

---

## 3. Summary of Proposed Pipeline Upgrades

| Pipeline Area | Current Defect | Recommended Modification |
|---|---|---|
| **Animation Resolution** | Omitted `view` config defaults to 512x512 window. | Explicitly add `view: { WINDOW_DIMENSIONS: [1080, 1080] }` in `mvc_yaml`. |
| **Camera & Framing** | Uncalibrated camera position. | Set `CAMERA_POS: [0.0, 0.0, 3.5]` and `CAMERA_FWD: [0.0, 0.0, -1.0]`. |
| **Character Position** | Character off-center depending on retarget defaults. | Specify `char_starting_location: [0.0, 0.0, 0.0]` in retarget config. |
| **Motion Scaling** | Default motion scale causes clipping/shrinking. | Set `scale` in `motion_cfg` tuned to character proportions. |
| **Audio Generation** | Hardcoded `audio_length_in_s=2.0`. | Dynamically set `audio_length_in_s = float(scene_duration)`. |
| **Audio Stitching** | `audio_loop` repetition or `set_duration` silence padding. | Match AudioLDM generation length to `clip.duration`; use silence fallback for empty prompts. |
