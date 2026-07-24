# Handoff Report — Animation (AnimatedDrawings) & Audio (AudioLDM) Pipeline Exploration

## 1. Observation
- **AnimatedDrawings Configuration**:
  - `ad_config.py` defines `Config`, `ViewConfig`, `SceneConfig`, `ControllerConfig`, `CharacterConfig`, `RetargetConfig`, and `MotionConfig`.
  - In `runpod_backend/server.py` (lines 195–206) and `runpod_backend/handler.py` (lines 105–108), dynamically created `mvc_yaml` files contain only `scene:` and `controller:` sections. The `view:` section is missing entirely.
  - `ViewConfig` parameters controlling resolution and camera are `WINDOW_DIMENSIONS` (default 512x512 when unassigned), `CAMERA_POS` (default `[0.0, 0.0, 0.0]`), `CAMERA_FWD`, and `CLEAR_COLOR`.
  - Character positioning and scaling are defined in `RetargetConfig` (`char_starting_location`, default `[0.0, 0.0, 0.0]`) and `MotionConfig` (`scale` parameter).
- **AudioLDM Generation & Stitching**:
  - `runpod_backend/server.py` (line 236) and `runpod_backend/handler.py` (line 136) invoke AudioLDM with hardcoded parameter `audio_length_in_s=2.0`.
  - MoviePy audio stitching in `handler.py` (line 144) uses `audioclip.set_duration(clip.duration)` which pads audio with silence beyond 2.0 seconds.
  - `server.py` (line 247) uses `audio_loop(audio_clip, duration=clip.duration)` which loops sound effects continuously.
  - Scenes without `sfx_prompt` create clips without audio tracks, causing concatenation issues in `concatenate_videoclips`.

## 2. Logic Chain
1. **Animation Framing & Centering**:
   - Because `mvc_yaml` generated at runtime omits `view:`, AnimatedDrawings uses fallback defaults for `WINDOW_DIMENSIONS` and `CAMERA_POS`.
   - Without explicit `char_starting_location` in retargeting and `scale` in motion config, characters render at standard resolution without guaranteed vertical or horizontal centering.
   - Therefore, adding an explicit `view:` section with `WINDOW_DIMENSIONS: [1080, 1080]`, `CAMERA_POS`, and setting `char_starting_location: [0.0, 0.0, 0.0]` will center the character and produce crisp high-resolution video output.
2. **Audio Duration Sync & Stitching**:
   - AudioLDM is called with `audio_length_in_s=2.0`, generating only 2 seconds of audio regardless of scene length (e.g. 5 seconds).
   - MoviePy `set_duration` pads the remaining 3 seconds with dead silence, causing truncation perception. `audio_loop` loops 2s audio repeatedly, creating sound artifacts.
   - Passing dynamic `audio_length_in_s = float(clip.duration)` (or calculated scene duration) directly to AudioLDM allows AudioLDM to generate audio matching the full scene length natively. Adding a silent audio fallback for scenes without SFX guarantees robust concatenation.

## 3. Caveats
- AnimatedDrawings requires `xvfb-run` for headless GL context rendering on Linux GPU pods (`runpod_backend`).
- AudioLDM generation latency increases slightly with longer `audio_length_in_s` (e.g. ~10 inference steps for 5.0s audio vs 2.0s audio).
- Character centering is also influenced by original texture bounding box padding (handled in Milestone 1).

## 4. Conclusion
To complete Milestones 2 (R2 Animation Presentation) and 3 (R3 Audio Quality & Sync):
1. **AnimatedDrawings**: Modify `server.py` and `handler.py` to generate `mvc_yaml` containing explicit `view:` configuration (`WINDOW_DIMENSIONS`, `CAMERA_POS`, `CAMERA_FWD`, `CLEAR_COLOR`) and explicit retargeting/motion scaling parameters.
2. **AudioLDM**: Calculate dynamic scene duration `scene_duration = clip.duration` (or `scene['end_time'] - scene['start_time']`), pass `audio_length_in_s = float(scene_duration)` to `audioldm_pipe`, and inject a silent audio track for scenes without prompts to ensure seamless concatenation.

## 5. Verification Method
1. **Code Inspection**:
   - Inspect `runpod_backend/server.py` to verify `mvc_yaml` string template includes `view:` block (`WINDOW_DIMENSIONS`, `CAMERA_POS`, `CAMERA_FWD`).
   - Inspect `runpod_backend/server.py` to verify `audioldm_pipe` call uses dynamic `audio_length_in_s`.
2. **Programmatic / E2E Test**:
   - Run `python test_e2e.py` or execute a test job against `/generate`.
   - Verify output video file in `out/e2e_test/e2e_final.mp4`.
   - Measure video duration vs audio duration using `ffprobe` or `moviepy`: ensure audio duration equals video duration within 0.1s tolerance and contains no silent trailing gaps.
