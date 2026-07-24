## 2026-07-24T19:03:05Z
You are a Worker subagent assigned to implement Milestone 1 (R1: Enhance Character Generation) for the Doodler AI backend pipeline upgrade project.

Your Working Directory: c:\Users\badri\Story\.agents\worker_m1
Project Workspace Root: c:\Users\badri\Story

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task Objectives (Milestone 1 — R1):
1. **Prompt Enhancement**:
   - Update prompt construction in `runpod_backend/server.py` and `runpod_backend/handler.py` (and any related prompt builder helper functions).
   - Enforce strict character prompt templates that prepend key framing directives: `"full body character sheet, single isolated character, standing pose, symmetrical front view, A-pose, solid pure white background"` and append negative/safeguard directives so SDXL-Turbo generates full-body, uncropped, isolated characters.

2. **Texture Image Padding & Resizing**:
   - Implement texture image post-processing function (e.g., `process_character_texture()` or padding logic) for `texture.png` generation in `runpod_backend/server.py` and `runpod_backend/handler.py`.
   - After background removal (`rembg`), crop the character to its alpha bounding box, calculate uniform scaling to fit target canvas size (e.g., 512x512) while preserving aspect ratio and leaving a distinct white padding margin (e.g. 30px margin) on all 4 edges (top, bottom, left, right).
   - Paste the centered character onto a pure white (255, 255, 255) canvas. Ensure character pixels never bleed out or touch any outer edge.

3. **Programmatic Verification Script**:
   - Create a test script `tests/test_character_padding.py` (or update existing tests) that verifies generated/processed `texture.png` images.
   - The test script must check all 4 outer margins (top rows, bottom rows, left columns, right columns) of `texture.png` to confirm they consist entirely of white background pixels (RGB (255, 255, 255) within a small tolerance if compressed).

4. **Execution & Handoff**:
   - Run the test suite (`pytest tests/test_character_padding.py` and existing tests) to verify build and test success.
   - Write your implementation details to `c:\Users\badri\Story\.agents\worker_m1\changes.md` and handoff report to `c:\Users\badri\Story\.agents\worker_m1\handoff.md`.
   - Send a message to the orchestrator upon completion.
