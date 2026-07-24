## 2026-07-24T19:19:14Z
You are worker_m3 (teamwork_preview_worker).
Your Working Directory: c:\Users\badri\Story\.agents\worker_m3
Project Workspace Root: c:\Users\badri\Story

Objective: Execute Milestone 3 (R3: Upgrade Audio Quality & Sync) of the Doodler AI backend pipeline upgrade.

Detailed Tasks:
1. Audit and modify AudioLDM sound generation in `runpod_backend/server.py` and `runpod_backend/handler.py`.
2. Ensure dynamic scene duration `scene_duration = float(clip.duration)` (or calculated from scene start/end timings) is calculated and passed as `audio_length_in_s` to the AudioLDM pipeline call, replacing hardcoded 2.0s or fixed duration parameters.
3. Inject a silent audio track fallback for scenes without sound prompts (or empty sound prompts) so MoviePy `concatenate_videoclips` and audio merging do not fail or truncate audio when assembling the final video.
4. Create a programmatic verification test script `tests/test_audio_quality.py` checking that generated/associated audio duration dynamically matches video clip duration without truncation.
5. Execute unit and integration test suites (`pytest tests/test_audio_quality.py`, `pytest tests/test_character_padding.py`, `pytest tests/test_video_framing.py`) and verify all tests pass.
6. Write a comprehensive handoff report at `c:\Users\badri\Story\.agents\worker_m3\handoff.md` detailing modified files, exact changes, build/test commands executed, test results, and verification findings. Also update `c:\Users\badri\Story\.agents\worker_m3\progress.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
