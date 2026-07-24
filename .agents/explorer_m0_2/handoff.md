# Handoff Report: SDXL-Turbo Character Generation & Texture Padding Analysis

## 1. Observation
- **Model Initialisation**: In `runpod_backend/server.py` (lines 48-55) and `runpod_backend/handler.py` (lines 43-49), SDXL-Turbo is initialized via HuggingFace `diffusers`:
  ```python
  sd_pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
  ```
- **Prompt Construction**: In `runpod_backend/server.py` (lines 132-135) and `runpod_backend/handler.py` (lines 62-65), prompt construction is currently implemented as:
  ```python
  character_prompt = "A character design on a solid white background. "
  parts = spec.get("sketch", {}).get("parts", [])
  for p in parts:
      character_prompt += p.get("prompt", "") + ", "
  ```
  Quoted verbatim from `runpod_backend/server.py:132-135`.
- **Image Generation & Background Removal**: In `runpod_backend/server.py` (lines 143-149), `sd_pipe` generates an image with `num_inference_steps=2, guidance_scale=0.0`, followed by `rembg.remove(image)` and compositing onto a white canvas.
- **Texture Resizing & Saving**: In `runpod_backend/server.py` (lines 165-166), `texture.png` is saved to `/workspace/AnimatedDrawings/examples/characters/char1/texture.png` using:
  ```python
  im = Image.open(char_image_path).resize((w, h))
  im.save(os.path.join(ad_char_dir, "texture.png"))
  ```
  Quoted verbatim from `runpod_backend/server.py:165-166`.

## 2. Logic Chain
1. **Observation 1 & 2 (Prompt Construction)**: Current character prompts rely on simple string concatenation without strict directives for full body, standing pose, front view, symmetrical alignment, or character sheet layout.
2. **Deduction 1**: Without framing and pose directives in the prompt, SDXL-Turbo generates cropped body parts (close-up headshots, half-torsos), leading to characters bleeding off image borders.
3. **Observation 3 & 4 (Texture Resizing)**: Direct resizing `im.resize((w, h))` deforms the aspect ratio of the 512x512 image to fit rectangular targets (e.g., 454x602) without considering character bounding boxes or margins.
4. **Deduction 2**: If the generated character touches the image border, direct resizing retains character pixels on the outer boundary. AnimatedDrawings requires clean white margins around all 4 edges to detect contours and skeleton joints properly.
5. **Synthesis & Solution**: 
   - Refactor prompt construction to prepend strict framing tokens (`"full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background"`) and append safeguard negative tokens (`"full body visible, head to toe, centered in frame, pure white background, no crop"`).
   - Refactor `texture.png` creation by calculating the RGBA bounding box (`alpha.getbbox()`), scaling the cropped character into target dimensions minus margin (e.g. 30px padding), and centering it on a white canvas.

## 3. Caveats
- **Environment Execution**: The actual SDXL-Turbo GPU pipeline runs inside the RunPod container environment (`runpod_backend/server.py` / `handler.py`), which requires CUDA for GPU inference. Local static code analysis was conducted without executing PyTorch CUDA calls.
- **Rembg Behavior**: `rembg` requires ONNX runtime in the container environment; the proposed bounding box algorithm relies on `img_no_bg.split()[3]` (the alpha channel returned by `rembg`).

## 4. Conclusion
- The image generation pipeline components in `runpod_backend/server.py` and `runpod_backend/handler.py` require two modifications:
  1. A strict prompt construction helper function (`build_strict_character_prompt()`) ensuring full body, isolated, standing, symmetrical character generation.
  2. An aspect-ratio preserving bounding box padding function (`process_character_texture()`) guaranteeing a white margin (e.g., 30px) along all 4 edges of `texture.png`.

## 5. Verification Method
1. **Code Inspection**:
   - Verify `runpod_backend/server.py` and `runpod_backend/handler.py` contain `build_strict_character_prompt` and `process_character_texture`.
2. **Programmatic Padding Test**:
   - Write a test script (e.g., `tests/test_character_padding.py`) that generates or processes a sample image into `texture.png`, inspects the 4 outer border lines (top row, bottom row, left column, right column), and asserts all boundary pixels are pure white `(255, 255, 255)`.
3. **Invalidation Conditions**:
   - If any pixel along the 4 outer edges of `texture.png` has a non-white RGB value (e.g., R<250 or G<250 or B<250), the test fails.
