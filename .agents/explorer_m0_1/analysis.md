# Doodler AI Codebase Analysis Report

## Executive Summary
This document provides a complete technical analysis of the Doodler AI project codebase (`c:\Users\badri\Story`). The application is a 2D AI-powered sketch generation, animation, audio synthesis, and video rendering pipeline. It features a **FastAPI** web backend running on RunPod (with serverless handler fallbacks), a **Streamlit** multi-phase web frontend, a **LangGraph** multi-agent orchestration graph, and an integrated generative pipeline (SDXL-Turbo, AnimatedDrawings, AudioLDM, MoviePy/FFmpeg).

---

## 1. Directory Structure & Key Components

```
c:\Users\badri\Story\
├── app.py                     # Streamlit frontend application (3-phase UI: Input, Review, Render)
├── doodler_pipeline.py        # Main Python workflow pipeline linking IR models and code emitters
├── doodler_ir.py              # Pydantic v2 domain models (DoodlerStudioSpec, SketchSequence, TimelineSequence)
├── scene_ir.py                # Richer 2D scene IR model (SceneIR, ShotIR, CharacterIR, CameraIR)
├── studio_spec.py             # Code-first shot control specification model (StudioSpec, ShotControl)
├── story_cli.py               # CLI runner entry point (`story-studio`)
├── requirements.txt           # Main Python dependencies list
├── pyproject.toml             # Package setup, module discovery, and pytest configuration
├── Dockerfile                 # Root container definition
│
├── runpod_backend/            # Backend service designed for RunPod deployment
│   ├── server.py              # FastAPI server implementing /generate, /status/{job_id}, /update_code
│   ├── handler.py             # RunPod serverless handler interface (runpod.serverless.start)
│   ├── Dockerfile             # RunPod container image setup
│   ├── requirements.txt       # Backend specific dependencies (diffusers, torch, rembg, moviepy)
│   └── setup_pod.sh           # Environment setup shell script for RunPod
│
├── agents/                    # LangGraph multi-agent system & prompt components
│   ├── studio_graph.py        # LangGraph StateGraph (StudioState, update_drafts, storywriter)
│   ├── sketch_planner_agent.py# Agent planning character body parts sequence
│   ├── timeline_director_agent.py # Agent directing animation scenes and timing
│   ├── storywriter_agent.py   # Agent handling Persian screenplay conversation
│   └── ...                    # 20+ specialized agents (render_agent, prompt_craft_agent, etc.)
│
├── llm/                       # LLM integration helpers
│   └── deepseek_client.py     # OpenAI-compatible API client configuration
│
├── tools/                     # Code generation emitters & utility functions
│   ├── animated_drawings_emitter.py # Emits stand-alone AnimatedDrawings execution scripts
│   ├── doodlergan_emitter.py  # Emits stand-alone DoodlerGAN execution scripts
│   └── studio_api.py          # Spec compilation & rendering helpers
│
├── tests/                     # Test suite containing 41 test files
│   ├── test_doodler_pipeline.py
│   ├── test_studio_api.py
│   ├── test_studio_graph.py
│   └── ...
│
├── deploy_to_pod.py           # Deployment script uploading code to RunPod
├── direct_runpod_test.py      # RunPod serverless runner test script
├── test_client.py             # HTTP client test querying /generate on FastAPI backend
└── test_e2e.py                # End-to-end integration test (LangGraph -> Pydantic -> RunPod API -> MP4)
```

---

## 2. Backend Web Framework & `/generate` Endpoint Implementation

### Framework & Launch Method
- **Framework**: FastAPI (`from fastapi import FastAPI, Request, BackgroundTasks` in `runpod_backend/server.py:12, 16`).
- **Server Initialization & Launch**:
  - Main app instance: `app = FastAPI(title="Doodler AI Backend")` (`runpod_backend/server.py:16`).
  - Startup Event (`runpod_backend/server.py:57-62`): On `@app.on_event("startup")`, a background thread runs `init_models()` so that the FastAPI HTTP server binds immediately to port `8000`.
  - Command to launch: Executed via Uvicorn (e.g., `uvicorn runpod_backend.server:app --host 0.0.0.0 --port 8000`).

### The `/generate` API Endpoint (`runpod_backend/server.py:92-110`)
```python
@app.post("/generate")
async def generate_video(request: Request, background_tasks: BackgroundTasks):
```
1. **Input Payload**: Expects JSON containing `"spec"` (conforming to `DoodlerStudioSpec`).
2. **Job Queueing**:
   - Generates a unique UUID (`job_id = str(uuid.uuid4())`).
   - Initializes job state in global dictionary: `JOBS[job_id] = {"status": "processing", "video_base64": None, "error": None}`.
   - Enqueues heavy rendering asynchronously via `background_tasks.add_task(process_video_job, job_id, spec)`.
3. **HTTP Response**: Immediately returns HTTP 200 JSON: `{"status": "success", "job_id": job_id, "message": "Job added to queue"}`.
4. **Status Endpoint** (`runpod_backend/server.py:111-115`): `@app.get("/status/{job_id}")` returns current status and base64 video data upon completion.

---

## 3. Pipeline Step Chaining (`process_video_job` in `runpod_backend/server.py:117-274`)

The pipeline execution flow sequentially processes images, animation scenes, audio synthesis, and final video assembly:

```
[Incoming Spec Payload]
          │
          ▼
┌───────────────────────────┐
│ 1. Image Generation       │ -> Model: stabilityai/sdxl-turbo (CUDA float16, 2 steps)
│    (SDXL-Turbo + rembg)   │ -> Prompt: spec.sketch.parts[*].prompt
└─────────┬─────────────────┘ -> Output: /tmp/character_{job_id}.png -> Char texture
          │
          ▼
┌───────────────────────────┐
│ 2. Animation Generation   │ -> Tool: AnimatedDrawings (xvfb-run -a python -m animated_drawings.render)
│    (AnimatedDrawings)     │ -> Motion Mapping: walk->zombie, jump->jumping, dance->jesse_dance, etc.
└─────────┬─────────────────┘ -> Output: /tmp/scene_{job_id}_{i}.mp4 per scene
          │
          ▼
┌───────────────────────────┐
│ 3. Audio SFX Generation   │ -> Model: cvssp/audioldm-s-full-v2 (CUDA, 10 steps)
│    (AudioLDM)             │ -> Prompt: scene.sfx_prompt
└─────────┬─────────────────┘ -> Output: /tmp/sfx_{job_id}_{i}.wav per scene
          │
          ▼
┌───────────────────────────┐
│ 4. Video & Audio Assembly │ -> Tool: MoviePy (VideoFileClip, audio_loop, concatenate_videoclips)
│    (MoviePy / FFmpeg)     │ -> Sync: Audio looped to match video clip duration exactly
└─────────┬─────────────────┘ -> Output: /tmp/final_{job_id}.mp4 -> base64 string in JOBS[job_id]
```

### Detailed Pipeline Components:

1. **Step 1: Character Image Generation (`runpod_backend/server.py:130-167`)**
   - Model: `stabilityai/sdxl-turbo` (`AutoPipelineForText2Image`).
   - Prompt assembly: Combines part prompts from `spec.get("sketch", {}).get("parts", [])`.
   - Background removal: Passes generated image through `rembg.remove()`, composite onto a clean white background `(255, 255, 255)`.
   - Texture Injection: Resizes and saves to `/workspace/AnimatedDrawings/examples/characters/char1/texture.png`.

2. **Step 2: Scene Animation (`runpod_backend/server.py:168-229`)**
   - Iterates through scenes in `spec.get("timeline", {}).get("scenes", [])`.
   - Motion mapping dictionary (`lines 179-186`):
     - `"walk"` -> `("zombie", "fair1_spf")`
     - `"jump"` -> `("jumping", "fair1_spf")`
     - `"dance"` -> `("jesse_dance", "mixamo_fff")`
     - `"wave"` -> `("wave_hello", "fair1_spf")`
     - `"dab"` -> `("dab", "fair1_spf")`
     - `"jumping_jacks"` -> `("jumping_jacks", "cmu1_pfp")`
   - Generates MVC YAML configuration file `/tmp/mvc_{job_id}_{i}.yaml`.
   - Subprocess invocation: Runs `xvfb-run -a python -m animated_drawings.render <mvc_yaml>` with `PYTHONPATH=/workspace/AnimatedDrawings`.

3. **Step 3: Audio Foley/SFX Generation (`runpod_backend/server.py:231-239`)**
   - Model: `cvssp/audioldm-s-full-v2` (`AudioLDMPipeline`).
   - Prompt: `scene.get("sfx_prompt", "")`.
   - Output: 16kHz WAV file written using `scipy.io.wavfile.write(out_audio_path, 16000, audio)`.

4. **Step 4: Video Concatenation & Audio-Video Synchronization (`runpod_backend/server.py:240-267`)**
   - Reads video scene clip with `moviepy.editor.VideoFileClip(out_video_path)`.
   - Reads audio scene clip with `moviepy.editor.AudioFileClip(out_audio_path)`.
   - Loops audio to match exact video clip duration using `moviepy.audio.fx.audio_loop.audio_loop(audio_clip, duration=clip.duration)`.
   - Binds audio to video clip via `clip.set_audio(audio_clip)`.
   - Concatenates all scene clips into single video with `concatenate_videoclips(video_clips)`.
   - Writes MP4 via `final_video.write_videofile(final_path, codec="libx264", audio_codec="aac")`.
   - Encodes final MP4 to base64 string stored in `JOBS[job_id]["video_base64"]`.

---

## 4. Dependencies & Operational Stack

From `requirements.txt` & `pyproject.toml`:
- **Web Backend & Network**: `fastapi`, `uvicorn`, `httpx`, `requests`
- **Data Validation & Domain Models**: `pydantic>=2.7.0,<3.0.0`, `typing_extensions`
- **Agent Orchestration**: `langgraph>=0.2.0`, `langgraph-checkpoint`, `langgraph-checkpoint-sqlite`
- **Frontend UI**: `streamlit>=1.32.0,<2.0.0`
- **Machine Learning & Image Processing**: `torch>=2.0.0`, `torchvision`, `diffusers`, `Pillow>=10.0.0`, `opencv-python-headless`, `rembg`
- **Audio Processing**: `librosa`, `soundfile`, `pydub`, `pyttsx3`, `gTTS`, `scipy`
- **Video Assembly**: `moviepy`, `ffmpeg-python`
- **Testing & Quality Assurance**: `pytest>=8.0.0`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`

---

## 5. Existing Test Setup

- **Test Framework**: `pytest` configured via `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["."]
  ```
- **Test Locations**: 41 test files residing in `c:\Users\badri\Story\tests\`.
- **Key Test Files**:
  - `tests/test_doodler_pipeline.py`: Tests the Doodler pipeline logic (`run_doodle_pipeline`) including happy path, empty LLM responses, and duration auto-corrections.
  - `tests/test_studio_api.py`: Tests code-first `StudioSpec` roundtrips, compilation, and rendering.
  - `tests/test_studio_graph.py`: Tests LangGraph studio graph behavior.
  - `test_e2e.py` (root level): Tests end-to-end integration across Phase 1 (LangGraph), Phase 2 (Pydantic Spec Validation), Phase 3 (RunPod POST submission), and Phase 4 (Polling status and downloading final MP4).
