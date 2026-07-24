# Forensic Audit Report — Milestone 1 (R1: Character Generation)

**Work Product**: `runpod_backend/character_utils.py`, `runpod_backend/server.py`, `runpod_backend/handler.py`, `tests/test_character_padding.py`  
**Profile**: General Project (Forensic Integrity)  
**Verdict**: **CLEAN**

---

## 1. Observation

### 1.1 Scope of Inspection
Audited the following files created/modified for Milestone 1:
- `runpod_backend/character_utils.py` (lines 1 to 90)
- `runpod_backend/server.py` (lines 18 to 21, 137 to 149, 166 to 172)
- `runpod_backend/handler.py` (lines 23 to 26, 65 to 77, 85 to 91)
- `tests/test_character_padding.py` (lines 1 to 173)

### 1.2 Direct Code Observations

#### A. Prompt Engineering (`runpod_backend/character_utils.py`, lines 8–43)
```python
PREFIX_DIRECTIVE = "full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background"
SAFEGUARD_DIRECTIVE = "full body visible, head to toe, centered in frame, pure white background, no crop"

def build_strict_character_prompt(spec: dict) -> str:
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
```

#### B. Texture Processing (`runpod_backend/character_utils.py`, lines 45–89)
```python
def process_character_texture(
    img_no_bg: Image.Image,
    target_size: tuple[int, int] = (512, 512),
    margin: int = 30,
) -> Image.Image:
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
```

#### C. Test Verification Logic (`tests/test_character_padding.py`, lines 21–52)
- Programmatic array slicing inspection in `verify_outer_margins_white`:
  - Top margin: `arr[0:margin, :, :]`
  - Bottom margin: `arr[h-margin:h, :, :]`
  - Left margin: `arr[:, 0:margin, :]`
  - Right margin: `arr[:, w-margin:w, :]`
  - Computes `max_diff = np.max(np.abs(region.astype(int) - white.astype(int)))` and enforces `max_diff <= tolerance`.

### 1.3 Forensic Prohibited Pattern Check Results

| Check # | Prohibited Pattern | Status | Empirical Observation |
|---|---|---|---|
| 1 | **Hardcoded test results** | **PASS** | No static/hardcoded prompts or fake outputs returned in `character_utils.py`. Prompts and image canvas are constructed dynamically. |
| 2 | **Facade implementations** | **PASS** | Genuine algorithm implementations. PIL bounding box crop (`getbbox`), aspect-ratio scaling (`min(max_w/crop_w, max_h/crop_h)`), and paste centered on fresh RGB white canvas `(255, 255, 255)` are present and functional. |
| 3 | **Fabricated verification outputs** | **PASS** | Workspace search confirmed zero pre-populated log files, fake test results, or cached output artifacts predating the execution. |
| 4 | **Self-certifying tests** | **PASS** | Tests in `test_character_padding.py` programmatically construct dynamic PIL images with solid red/blue fill reaching the boundaries `[0, 0, 400, 400]`, execute `process_character_texture()`, and perform pixel matrix verification using `numpy`. |
| 5 | **Execution delegation** | **PASS** | Image processing uses Pillow standard library routines without delegating core padding logic to external black-box binaries. |

---

## 2. Logic Chain

1. **Prompt Construction Veracity**:
   - Observation 1.2.A shows `build_strict_character_prompt(spec)` dynamically traverses `spec['sketch']['parts']`, fallback keys (`character_prompt`, `prompt`, `brief.user_prompt`), or defaults to `"character design"`.
   - Prepends `PREFIX_DIRECTIVE` ("full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background") and appends `SAFEGUARD_DIRECTIVE` ("full body visible, head to toe, centered in frame, pure white background, no crop").
   - Logic is strictly dynamic, context-aware, and free of hardcoded returns.

2. **Image Scaling & Padding Accuracy**:
   - Observation 1.2.B shows `process_character_texture` crops the image to its non-zero alpha bounding box `alpha.getbbox()`.
   - Computes `max_w = target_w - 2 * margin` and `max_h = target_h - 2 * margin`.
   - Scale factor `scale = min(max_w / crop_w, max_h / crop_h)` preserves aspect ratio.
   - Offsets `offset_x = (target_w - new_w) // 2` and `offset_y = (target_h - new_h) // 2` mathematically guarantee `offset_x >= margin` and `offset_y >= margin`, leaving all 4 outer margins `[0..margin-1]` and `[dimension-margin..dimension-1]` untouched pure white `(255, 255, 255)`.

3. **Backend Integration**:
   - Observation 1.1 confirms both `runpod_backend/server.py` and `runpod_backend/handler.py` import and call `build_strict_character_prompt(spec)` and `process_character_texture(img_no_bg, ...)` during image generation and character texture preparation.

4. **Test Suite Integrity**:
   - Observation 1.2.C shows unit tests evaluate outer margin pixel matrices independently via `verify_outer_margins_white`, testing 500x300, 400x100 (wide), 100x400 (tall), transparent empty images, and saved PNG roundtrips.

---

## 3. Caveats

1. **Defensive Coding Edge Case**:
   - If an input dictionary contains explicit `None` values for sub-keys (e.g. `{"sketch": None}` or `{"brief": None}`), `spec.get("sketch", {})` evaluates to `None`, causing `None.get("parts", [])` to raise an `AttributeError`. (Recommendation: update helper to `(spec.get("sketch") or {}).get(...)`). This is a minor input validation caveat, not an integrity violation.
2. **Terminal Execution Timeout**:
   - Direct execution of `pytest` via `run_command` timed out waiting for shell approval prompt. Static analysis and manual mathematical verification were executed to validate all assertions and calculations.

---

## 4. Conclusion

**VERDICT**: **CLEAN**

Milestone 1 (R1: Character Generation) implementation is authentic, dynamic, and clean of integrity violations. Prompt construction correctly enforces A-pose standing directives, and texture image post-processing guarantees uniform scaling with pure white padding margins along all 4 outer boundaries.

---

## 5. Verification Method

- **Files to Inspect**:
  - `runpod_backend/character_utils.py`
  - `runpod_backend/server.py`
  - `runpod_backend/handler.py`
  - `tests/test_character_padding.py`
- **Verification Command**:
  ```bash
  pytest tests/test_character_padding.py
  ```
- **Invalidation Conditions**:
  - `test_character_padding.py` failing on any margin check.
  - Any hardcoded static prompt string being substituted in place of input `spec` processing.
  - Any pixel in outer margins `0..margin-1` or `dim-margin..dim-1` deviating from `(255, 255, 255)`.
