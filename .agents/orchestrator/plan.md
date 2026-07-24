# Project Execution Plan — Doodler AI Backend Pipeline Upgrade

## Phase 1: Codebase Exploration & Pipeline Analysis (Milestone 0)
- Objective: Understand repository structure, existing code in `c:\Users\badri\Story`, pipeline architecture for `/generate`, image generation code, AnimatedDrawings config, AudioLDM integration, and existing tests.
- Workers: 3 `teamwork_preview_explorer` subagents to perform parallel investigation.

## Phase 2: Implementation (Milestones 1, 2, 3)
- Milestone 1 (R1): SDXL-Turbo Character Generation & Image Padding
  - Implement prompt templates ("full body, isolated, symmetrical, character sheet")
  - Add image padding/resizing to ensure white border around character in `texture.png`.
- Milestone 2 (R2): AnimatedDrawings Presentation Upgrade
  - Modify `mvc_yaml` or character config scale and position parameters for centering and professional framing.
- Milestone 3 (R3): AudioLDM Quality & Duration Sync
  - Refine sound effect pipeline, ensure audio length matches animation length without truncation.

## Phase 3: Verification & Integration (Milestone 4)
- Run Character Padding verification script.
- Run Video Framing configuration test.
- Run End-to-End backend test on `/generate` endpoint, verifying MP4 output and audio-video duration match.
- Forensic audit for zero-tolerance integrity check.
