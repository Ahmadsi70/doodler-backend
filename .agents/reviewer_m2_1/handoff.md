# Review & Handoff Report — Milestone 2 (R2: Improve Animation Presentation)

## Review Summary

**Verdict**: REQUEST_CHANGES

The implementation of Milestone 2 (R2: Improve Animation Presentation) successfully introduces standardized helper functions `build_mvc_yaml_dict` and `generate_mvc_yaml` in `runpod_backend/character_utils.py` and updates `ad_config.py` to allow `char_starting_location` and `scale` overrides. `tests/test_video_framing.py` correctly tests these configuration generators and `ad_config` overrides.

However, a **Critical functional defect** was identified in `runpod_backend/handler.py`. In `handler.py`, the old pre-M2 check for `/workspace/AnimatedDrawings/video.mp4` was left unchanged after introducing `generate_mvc_yaml(..., output_video_path=out_video_path, ...)`. Because AnimatedDrawings now writes output directly to `out_video_path` (`/tmp/scene_{i}.mp4`), `/workspace/AnimatedDrawings/video.mp4` is never created. As a result, `handler.py` always evaluates `if os.path.exists(default_vid)` as `False`, sets `out_video_path = "mock"`, discards the actual rendered video clip, and returns a dummy 24-byte empty MP4 base64 string (`"AAAAGGZ0eXBtcDQyAAAAAWlzb21tcDQy"`).

---

## 1. Observation

1. **`runpod_backend/character_utils.py`**:
   - Added `build_mvc_yaml_dict` (lines 92–134) and `generate_mvc_yaml` (lines 137–155).
   - Correctly includes `view:` section parameters: `WINDOW_DIMENSIONS` (`[1080, 1080]`), `CAMERA_POS` (`[0.0, 0.0, 3.5]`), `CAMERA_FWD` (`[0.0, 0.0, -1.0]`), `CLEAR_COLOR` (`[1.0, 1.0, 1.0, 1.0]`).
   - Correctly includes character entry parameters: `char_starting_location` (`[0.0, 0.0, 0.0]`) and `scale` (`1.0`).

2. **`ad_config.py`**:
   - Updated `SceneConfig.__init__` (lines 95–98) to read `char_starting_location` and `scale` from character dictionaries in `scene_cfg['ANIMATED_CHARACTERS']` and override `retarget_cfg.char_start_loc` and `motion_cfg.scale`.

3. **`runpod_backend/server.py`**:
   - Updated lines 202–215 to call `generate_mvc_yaml(...)` with framing options (`window_dimensions=(1080, 1080)`, `camera_pos=[0.0, 0.0, 3.5]`, `camera_fwd=[0.0, 0.0, -1.0]`, `clear_color=[1.0, 1.0, 1.0, 1.0]`, `char_starting_location=[0.0, 0.0, 0.0]`, `scale=1.0`).
   - Line 236 correctly checks `if not os.path.exists(out_video_path): out_video_path = "mock"`.

4. **`runpod_backend/handler.py`**:
   - Lines 130–141 updated to call `generate_mvc_yaml(...)` with output path `out_video_path` (`/tmp/scene_{i}.mp4`).
   - Lines 164–169 contain obsolete post-processing logic:
     ```python
     default_vid = "/workspace/AnimatedDrawings/video.mp4"
     if os.path.exists(default_vid):
         os.rename(default_vid, out_video_path)
     else:
         out_video_path = "mock"
     ```
     This check fails because AnimatedDrawings output was redirected to `/tmp/scene_{i}.mp4`.

5. **`tests/test_video_framing.py`**:
   - Added unit tests: `test_build_mvc_yaml_dict_defaults`, `test_generate_mvc_yaml_string_parsing`, `test_custom_framing_parameters`, `test_ad_config_scene_config_override_logic`.

---

## 2. Logic Chain

1. `generate_mvc_yaml` sets `controller.OUTPUT_VIDEO_PATH` inside the generated `/tmp/mvc_{i}.yaml` file to `out_video_path` (`/tmp/scene_{i}.mp4`).
2. When `animated_drawings.render` is invoked with `/tmp/mvc_{i}.yaml`, AnimatedDrawings writes the rendered MP4 file directly to `/tmp/scene_{i}.mp4`.
3. In `runpod_backend/handler.py`, lines 164–165 check if `/workspace/AnimatedDrawings/video.mp4` exists. Since AnimatedDrawings wrote to `/tmp/scene_{i}.mp4` instead, `/workspace/AnimatedDrawings/video.mp4` does NOT exist.
4. Line 169 in `handler.py` sets `out_video_path = "mock"`.
5. Line 178 `if out_video_path != "mock":` is evaluated as `False`, skipping clip loading and concatenation.
6. Line 196 returns `b64_vid = "AAAAGGZ0eXBtcDQyAAAAAWlzb21tcDQy"` (a dummy 24-byte empty MP4 base64 payload).
7. Therefore, `runpod_backend/handler.py` fails to deliver rendered video to callers on RunPod serverless execution.

---

## 3. Findings

### [Critical] Finding 1: Broken Output Video Path Resolution in `runpod_backend/handler.py`
- **What**: `runpod_backend/handler.py:164-169` checks for `/workspace/AnimatedDrawings/video.mp4` instead of checking if `out_video_path` (`/tmp/scene_{i}.mp4`) exists.
- **Where**: `runpod_backend/handler.py`, lines 164–169.
- **Why**: `generate_mvc_yaml` passes `output_video_path=out_video_path` to AnimatedDrawings. AnimatedDrawings renders directly to `/tmp/scene_{i}.mp4` and never creates `/workspace/AnimatedDrawings/video.mp4`. The check fails every time, forcing `out_video_path = "mock"` and returning empty base64 video data.
- **Suggestion**: Update lines 164–169 of `runpod_backend/handler.py` to:
  ```python
  if not os.path.exists(out_video_path):
      default_vid = "/workspace/AnimatedDrawings/video.mp4"
      if os.path.exists(default_vid):
          os.rename(default_vid, out_video_path)
      else:
          out_video_path = "mock"
  ```

### [Major] Finding 2: Missing `PYTHONPATH` Environment Variable in `runpod_backend/handler.py` Subprocess
- **What**: `subprocess.run(render_cmd, cwd="/workspace/AnimatedDrawings", capture_output=True, text=True, check=True)` does not specify `env` with `PYTHONPATH="/workspace/AnimatedDrawings"`.
- **Where**: `runpod_backend/handler.py`, line 153.
- **Why**: `server.py:224` explicitly includes `env["PYTHONPATH"] = "/workspace/AnimatedDrawings"`. Omitting `PYTHONPATH` in `handler.py` can cause `ModuleNotFoundError: No module named 'animated_drawings'` when invoked in certain execution environments.
- **Suggestion**: Add `env = os.environ.copy(); env["PYTHONPATH"] = "/workspace/AnimatedDrawings"` to `subprocess.run` in `handler.py`.

### [Minor] Finding 3: Mutable Default Parameter List Signatures in `character_utils.py`
- **What**: `build_mvc_yaml_dict` uses mutable default list arguments `camera_pos: list[float] = [0.0, 0.0, 3.5]`, `camera_fwd: list[float] = [0.0, 0.0, -1.0]`, `clear_color: list[float] = [1.0, 1.0, 1.0, 1.0]`, `char_starting_location: list[float] = [0.0, 0.0, 0.0]`.
- **Where**: `runpod_backend/character_utils.py`, lines 98–101.
- **Why**: Using mutable default lists in Python signatures is a risk for accidental in-place mutations across invocations.
- **Suggestion**: Replace default list parameters with `None` or immutable tuples.

---

## 4. Verified Claims

- `build_mvc_yaml_dict` creates dict containing `view: {WINDOW_DIMENSIONS, CAMERA_POS, CAMERA_FWD, CLEAR_COLOR}`, `scene: {ANIMATED_CHARACTERS: [{char_starting_location, scale}]}`, `controller: {MODE, OUTPUT_VIDEO_PATH, OUTPUT_VIDEO_CODEC}` → Verified via source code inspection → PASS
- `generate_mvc_yaml` serializes valid YAML string with all required parameters → Verified via source code inspection and unit tests in `test_video_framing.py` → PASS
- `ad_config.SceneConfig` overrides `retarget_cfg.char_start_loc` and `motion_cfg.scale` → Verified via source code inspection → PASS
- `runpod_backend/server.py` correctly handles rendered output file check (`if not os.path.exists(out_video_path): out_video_path = "mock"`) → Verified via source code inspection → PASS
- `runpod_backend/handler.py` correctly handles rendered video output → Verified via source code inspection → FAIL (Critical Finding 1)

---

## 5. Caveats

- `pytest tests/test_video_framing.py` tool command execution timed out on user permission in non-interactive mode. Verification was conducted via exhaustive static code analysis and logic tracing.
- Headless MESA GL rendering execution is skipped on non-Linux platforms without Xvfb installed.

---

## 6. Conclusion

Milestone 2 (R2: Improve Animation Presentation) verdict is **REQUEST_CHANGES**. The worker must fix the output video detection bug and missing `PYTHONPATH` environment setting in `runpod_backend/handler.py` before approval can be granted.

---

## 7. Verification Method

To independently verify after changes are applied:
1. Inspect `runpod_backend/handler.py` lines 150–170 to confirm `PYTHONPATH` environment is passed to `subprocess.run` and `if not os.path.exists(out_video_path):` is used for output video detection.
2. Run `pytest tests/test_video_framing.py`.
