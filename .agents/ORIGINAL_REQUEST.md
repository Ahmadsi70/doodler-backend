# Original User Request

## 2026-07-24T18:58:04Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Upgrading backend pipeline via teamwork_preview

Upgrade the Doodler AI backend pipeline to produce high-quality, polished character images, better synchronized and richer audio, and smoother, well-presented video animations.

Working directory: ~/teamwork_projects/doodler_pipeline_upgrade
Integrity mode: development

## Requirements

### R1. Enhance Character Generation (SDXL-Turbo)
Modify the image generation pipeline to use strict prompt templates (e.g., adding "full body, isolated, symmetrical, character sheet") and implement image padding/resizing so the character is completely visible and never cut off or half-finished.

### R2. Improve Animation Presentation (AnimatedDrawings)
Tweak the AnimatedDrawings configuration files (camera angle, character scale, resolution, etc.) to ensure the character is perfectly centered in the video and the presentation feels professional.

### R3. Upgrade Audio Quality (AudioLDM)
Refine the sound effect generation pipeline to produce richer audio that seamlessly matches the animation, ensuring high fidelity.

## Acceptance Criteria

### Programmatic & Objective Verification
- [ ] **Character Padding Test:** A Python script must verify that the generated `texture.png` has a margin of white pixels along all edges (ensuring the character isn't bleeding out of the frame).
- [ ] **Video Framing Test:** The `AnimatedDrawings` output configuration must be verifiable by checking the modified `mvc_yaml` or character config, ensuring the `scale` and `position` values are adjusted from their defaults to explicitly center the character.
- [ ] **End-to-End Run:** The backend must successfully process a complete job through `/generate` without crashing, producing an MP4 where the audio length exactly matches the video length without truncating.
