# Story Studio — Complete Library & Database Stack

All libraries are **free, open-source** unless marked otherwise.

---

## 📊 DATABASES

### Primary: SQLite (embedded, zero-config)
- **Package**: built-in (`sqlite3`) + `langgraph-checkpoint-sqlite`
- **Purpose**: Job state persistence, LangGraph checkpoints, session storage, character profiles, audio catalog
- **Why**: Zero setup, file-based, perfect for local studio. Already used for `studio_graph.db` checkpoints.
- **License**: Public Domain

### Vector Database: ChromaDB (embedded)
- **Package**: `chromadb>=0.5.0`
- **Purpose**: Semantic search across style catalog, prompt templates, character library. Find similar shots, recommend styles based on brief embedding.
- **Why**: Lightweight, embedded mode (no server needed), Python-native, LangChain-compatible.
- **Alternative**: **FAISS** (`faiss-cpu`) — Facebook AI Similarity Search, faster for large datasets but less user-friendly API.
- **License**: Apache 2.0

### Optional: LanceDB (serverless columnar)
- **Package**: `lancedb`
- **Purpose**: High-performance multimodal storage for frame data, shot tables, performance charts. Can store images + metadata in one table.
- **Why**: Built on Lance columnar format, zero-copy reads, great for 24fps per-frame data.
- **License**: Apache 2.0

### Key-Value Cache: diskcache
- **Package**: `diskcache>=5.6`
- **Purpose**: Cached agent outputs, compiled specs, rendered thumbnails. Avoids re-running expensive operations.
- **Why**: Pure Python, SQLite-backed, auto-expiring cache.
- **License**: Apache 2.0

---

## 🎵 AUDIO LIBRARIES

### Audio Processing: librosa
- **Package**: `librosa>=0.10.0`
- **Purpose**: Audio analysis for VO alignment, duration detection, waveform visualization, MFCC for phoneme extraction.
- **Why**: Industry standard for audio analysis in Python. Used for `vo_align.py` and `phoneme_sync_agent.py`.
- **License**: ISC

### Audio I/O: soundfile
- **Package**: `soundfile>=0.12.0`
- **Purpose**: Read/write WAV files (VO recordings, SFX cues). Faster and more reliable than scipy.io.wavfile.
- **Why**: Wraps libsndfile, supports all formats, handles 24-bit audio.
- **License**: BSD 3-Clause

### Audio Manipulation: pydub
- **Package**: `pydub>=0.25.0`
- **Purpose**: Simple audio slicing, concatenation, fade-in/out for foley timeline assembly. Volume normalization.
- **Why**: Extremely simple API, great for quick audio edits in `foley_timeline_agent.py`.
- **Note**: Requires `ffmpeg` on PATH.
- **License**: MIT

### Text-to-Speech (TTS): pyttsx3 + gTTS
- **Package**: `pyttsx3>=2.90` + `gTTS>=2.5`
- **Purpose**: Generate VO from dialogue text for phoneme sync and preview. 
  - `pyttsx3`: Offline TTS (uses OS speech engine — SAPI5 on Windows). No internet needed. Fast. Multiple voices.
  - `gTTS`: Google Text-to-Speech. Better quality, supports Persian (Farsi). Requires internet.
- **Why**: Free TTS for generating scratch VO tracks. Phoneme sync works against any audio.
- **License**: pyttsx3 (MIT), gTTS (MIT)

### Optional: Coqui TTS (open-source, multilingual)
- **Package**: `TTS>=0.22.0` (from Coqui AI)
- **Purpose**: High-quality neural TTS with Persian/Farsi voice models. Best quality for final VO.
- **Why**: Fully offline, 1000+ voices, supports voice cloning. Heavier dependency (~2GB models).
- **License**: Coqui Public License (free for non-commercial)

### Optional: pedalboard (Spotify)
- **Package**: `pedalboard>=0.8.0`
- **Purpose**: Audio effects (reverb, delay, EQ, compression) for foley and ambience. Studio-quality processing.
- **Why**: Extremely fast (C++ backend), used by Spotify. Great for polishing audio timeline.
- **License**: GPL v3

---

## 🎨 IMAGE & VIDEO

### Image Processing: Pillow (already) + opencv-python
- **Package**: `opencv-python-headless>=4.9.0`
- **Purpose**: Character image manipulation, composition overlays, thumbnail generation, frame extraction. More powerful than Pillow for pixel operations.
- **Why**: De facto standard for computer vision. Used for `pixel_qa.py` quality checks.
- **License**: Apache 2.0

### FFmpeg Binding: ffmpeg-python
- **Package**: `ffmpeg-python>=0.2.0`
- **Purpose**: Pythonic wrapper for FFmpeg CLI. Used in Light slideshow rendering, video concatenation (`chapter_concat.py`).
- **Why**: Clean API, handles all video/audio formats.
- **Note**: Requires `ffmpeg` binary on PATH.
- **License**: MIT

### Optional: moviepy
- **Package**: `moviepy>=2.0.0`
- **Purpose**: Higher-level video editing (transitions, text overlays, composite clips). Alternative to raw FFmpeg for simple slideshows.
- **Why**: Easier API for quick video assembly. Slower than raw FFmpeg but more flexible.
- **License**: MIT

### Optional: pygifsicle / imageio
- **Package**: `imageio>=2.34.0` + `imageio-ffmpeg`
- **Purpose**: Animated GIF previews, frame sequence export. Quick preview generator for shot animations.
- **Why**: Simple API, supports animated formats.
- **License**: BSD 2-Clause

---

## 🤖 AI / LLM

### OpenAI (already)
- **Package**: `openai>=1.40.0`
- **Purpose**: Optional LLM enrichment of agent outputs (better screenplay descriptions, smarter style recommendations).
- **Why**: Industry standard, supports GPT-4o.
- **License**: MIT (library), API is paid

### Anthropic Claude (optional)
- **Package**: `anthropic>=0.30.0`
- **Purpose**: Alternative LLM for longer context (200K tokens) — better for full screenplay analysis.
- **License**: MIT (library), API is paid

### Google Gemini (optional, free tier available)
- **Package**: `google-generativeai>=0.7.0`
- **Purpose**: LLM enrichment with free tier (60 requests/minute). Good Persian/Farsi support.
- **Why**: Free tier makes it the best option for personal use.
- **License**: Apache 2.0

### LiteLLM (unified LLM interface)
- **Package**: `litellm>=1.40.0`
- **Purpose**: Single API for all LLM providers (OpenAI, Anthropic, Gemini, Ollama local). Switch provider without code changes.
- **Why**: Future-proof. User can use free Gemini or local Ollama instead of paid OpenAI.
- **License**: MIT

### Optional: Ollama (local LLM, fully offline)
- **Tool**: [Ollama](https://ollama.com) — not a Python package, a separate install
- **Python bridge**: `ollama>=0.3.0` or via LiteLLM
- **Purpose**: Run LLMs locally (Llama 3, Mistral, Gemma). 100% free, no internet, no API keys.
- **Why**: Best for users who want full privacy and zero cost.

---

## 📝 TEXT / NLP

### Persian Text Processing: hazm
- **Package**: `hazm>=3.0.0`
- **Purpose**: Persian NLP toolkit — tokenization, stemming, lemmatization, POS tagging. Used for brief analysis and beat inference from Persian text.
- **Why**: Most popular Persian NLP library. Essential for Persian-first UI.
- **License**: MIT

### Multi-language: sentence-transformers
- **Package**: `sentence-transformers>=3.0.0`
- **Purpose**: Generate embeddings for semantic search (style matching, prompt retrieval, character similarity). Works with ChromaDB.
- **Why**: State-of-the-art for semantic similarity. Supports multilingual models (paraphrase-multilingual).
- **License**: Apache 2.0

### Optional: spacy
- **Package**: `spacy>=3.7.0`
- **Purpose**: Advanced NLP pipeline for action verb extraction, entity recognition in briefs.
- **Why**: Industrial-strength NLP. Good for extracting characters, objects, locations from narrative text.
- **License**: MIT

---

## 🎬 ANIMATION / MOTION

### easing-functions
- **Package**: `easing-functions>=1.0.0`
- **Purpose**: Animation easing curves (ease-in, ease-out, elastic, bounce) for camera movement and transitions.
- **Why**: Lightweight, pure Python. Used in `camera_curve_agent.py` for keyframe interpolation.
- **License**: MIT

### Optional: py-motion-editor
- **Package**: Not a standard package — implement as custom module
- **Purpose**: Simple keyframe editor data structures for performance charts.
- **Why**: Domain-specific, best implemented as part of the project.

---

## 🌐 WEB / NETWORK

### HTTP Client: httpx
- **Package**: `httpx>=0.27.0`
- **Purpose**: Async HTTP for cloud render uploads, external API calls (Gemini, style downloads).
- **Why**: Modern, async, HTTP/2 support. Better than requests for concurrent operations.
- **License**: BSD 3-Clause

### Optional: fastapi + uvicorn (if adding API server)
- **Package**: `fastapi>=0.110.0` + `uvicorn>=0.27.0`
- **Purpose**: REST API for remote job submission. Could replace Streamlit for headless operation.
- **Why**: Fastest Python web framework. Useful if adding a remote render API.
- **License**: MIT

---

## 📦 PACKAGING / DISTRIBUTION

### pyinstaller (optional)
- **Package**: `pyinstaller>=6.0.0`
- **Purpose**: Bundle Story Studio into a single .exe for Windows distribution. No Python required for end users.
- **Why**: Simplifies deployment for non-technical users.
- **License**: GPL (but not copyleft for generated exes)

### pip-tools
- **Package**: `pip-tools>=7.0.0`
- **Purpose**: Lock dependency versions (`pip-compile` → `requirements.lock`). Reproducible builds.
- **License**: BSD 3-Clause

---

## 🧪 TESTING / QUALITY

### Already needed:
- `pytest>=8.0.0` — test framework
- `pytest-asyncio>=0.23.0` — async test support (for LangGraph)
- `pytest-cov>=5.0.0` — code coverage
- `pytest-xdist>=3.5.0` — parallel test execution

### Optional: pytest-golden
- **Package**: `pytest-golden>=0.2.0`
- **Purpose**: Snapshot/golden file testing for `story_props.json` contract validation.
- **Why**: Ensures props contract never breaks between versions.
- **License**: MIT

---

## 🛠️ DEVELOPMENT TOOLS

- `ruff>=0.4.0` — Fast Python linter + formatter (replaces flake8, isort, black)
- `mypy>=1.9.0` — Static type checking
- `pre-commit>=3.7.0` — Git hooks for lint/format on commit
- `mkdocs-material>=9.5.0` — Documentation site generator (beautiful docs)

---

## 📋 COMPLETE requirements.txt

```text
# ── Core ──
pydantic>=2.7.0,<3.0.0
typing_extensions>=4.12.0
streamlit>=1.32.0,<2.0.0
python-dotenv>=1.0.0,<2.0.0

# ── Image ──
Pillow>=10.0.0,<12.0.0
opencv-python-headless>=4.9.0

# ── AI / LLM ──
openai>=1.40.0,<2.0.0
google-generativeai>=0.7.0
litellm>=1.40.0

# ── LangGraph ──
langgraph>=0.2.0
langgraph-checkpoint>=2.0.0
langgraph-checkpoint-sqlite>=2.0.0

# ── Vector Database ──
chromadb>=0.5.0

# ── Audio ──
librosa>=0.10.0
soundfile>=0.12.0
pydub>=0.25.0
pyttsx3>=2.90
gTTS>=2.5

# ── Video ──
ffmpeg-python>=0.2.0

# ── Text / NLP ──
hazm>=3.0.0
sentence-transformers>=3.0.0

# ── Cache ──
diskcache>=5.6

# ── Network ──
httpx>=0.27.0

# ── Animation ──
easing-functions>=1.0.0

# ── Testing ──
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0

# ── Dev Tools ──
ruff>=0.4.0
mypy>=1.9.0
```

---

## 🟢 Node.js (Remotion) — package.json

```json
{
  "dependencies": {
    "@remotion/cli": "4.0.493",
    "@remotion/renderer": "4.0.493",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "remotion": "4.0.493"
  },
  "devDependencies": {
    "@types/react": "18.3.12",
    "typescript": "5.6.3"
  }
}
```

All Remotion packages are **free** (Remotion is source-available, free for individuals and small teams).

---

## 🟡 External Tools (Free, not Python packages)

| Tool | Purpose | Install |
|------|---------|---------|
| **FFmpeg** | Video encoding, slideshow rendering, audio manipulation | `winget install ffmpeg` or https://ffmpeg.org |
| **Node.js** | Remotion runtime | `winget install nodejs` or https://nodejs.org |
| **Ollama** | Local LLM (free, offline) | https://ollama.com |
| **Git** | Version control | https://git-scm.com |

---

## 💰 Cost Summary

| Category | Cost |
|----------|------|
| All Python libraries | **$0** (all open-source) |
| All Node.js libraries | **$0** (Remotion free for individuals) |
| SQLite | **$0** (built-in) |
| ChromaDB | **$0** (Apache 2.0) |
| FFmpeg | **$0** |
| LLM (Gemini free tier) | **$0** (60 req/min) |
| LLM (Ollama local) | **$0** (runs on your hardware) |
| LLM (OpenAI API) | Paid (optional) |
| **Total for full local setup** | **$0** |

---

## 🔄 Database Strategy

```
SQLite (.story/studio.db)
  ├── jobs table          — job_id, status, created_at, brief, quality
  ├── checkpoints table   — LangGraph state snapshots
  ├── sessions table      — UI session persistence
  ├── characters table    — character profiles (name, layers, rig)
  └── audio_catalog table — SFX cues (name, path, category, duration)

ChromaDB (.story/vectors/)
  ├── styles collection   — visual style embeddings for recommendation
  ├── prompts collection  — prompt template embeddings for retrieval
  └── shots collection    — shot embeddings for similarity search

diskcache (.story/cache/)
  ├── agent_outputs/      — cached agent results per brief hash
  ├── compiled_specs/     — compiled StudioSpec artifacts
  └── thumbnails/         — generated image thumbnails
```

---

## 🚀 Quick Install (one command)

```powershell
# Python side
cd C:\Users\badri\Story
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Node.js side (Remotion)
cd remotion
npm install

# External tools
winget install ffmpeg
winget install nodejs

# Optional: local LLM
winget install ollama
ollama pull llama3.2
ollama pull gemma2
```