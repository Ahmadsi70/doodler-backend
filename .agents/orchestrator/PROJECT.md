# Project: Doodler AI Backend Pipeline Upgrade

## Architecture
- Backend API server (FastAPI / Flask / Python) processing requests via `/generate` endpoint
- Image Generation module (SDXL-Turbo) producing character texture maps
- Animation module (AnimatedDrawings) rendering 2D character animations
- Audio generation module (AudioLDM) generating sound effects synchronized with video duration
- Video assembly / stitching module merging animation frames and audio track into MP4

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 0 | Codebase Exploration | Analyze codebase, pipeline architecture, configuration files, and existing test setup | None | DONE |
| 1 | R1 Character Generation | Strict prompt templates, image padding/resizing for texture.png white margins | M0 | DONE |
| 2 | R2 Animation Presentation | AnimatedDrawings mvc_yaml/character config scale & position tuning | M0 | DONE |
| 3 | R3 Audio Quality & Sync | AudioLDM sound effect generation refinement & dynamic audio length matching | M0 | IN_PROGRESS |
| 4 | End-to-End Verification | E2E test execution, audio/video duration match, character white border test, mvc_yaml verification | M1, M2, M3 | PLANNED |

## Interface Contracts
- Character Image Generator (`runpod_backend/server.py` & `handler.py`): outputs `texture.png` with a margin of white pixels along all 4 edges.
- AnimatedDrawings Config (`runpod_backend/server.py` & `handler.py`): output configuration (`mvc_yaml` / character config) contains explicit `scale` and `position` / `view:` parameters centered away from default fallback.
- AudioLDM Generator (`runpod_backend/server.py` & `handler.py`): passes dynamic `audio_length_in_s` matching scene duration, producing audio whose length matches video duration exactly without truncation.
- `/generate` Endpoint: processes complete job without crashing, outputting MP4 with synchronized audio.

## Code Layout
- `runpod_backend/server.py`: FastAPI server, `/generate` endpoint, `process_video_job` pipeline execution.
- `runpod_backend/handler.py`: RunPod handler implementation for image, animation, audio generation.
- `doodler_ir.py`: Data models and specs (`DoodlerStudioSpec`, `SceneSpec`, etc.).
- `ad_config.py`: AnimatedDrawings configuration classes (`ViewConfig`, `CharacterConfig`, `RetargetConfig`, `MotionConfig`).
- `test_e2e.py`: End-to-end integration test runner.
- `tests/`: Unit and integration test directory (41 pytest modules).
