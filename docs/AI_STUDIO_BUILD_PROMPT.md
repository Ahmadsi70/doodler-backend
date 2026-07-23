# AI Studio Build Prompt — Story Studio with Full Library Stack

You already built the core Story Studio (animation pre-production pipeline with agents, LangGraph, Streamlit UI, and RubberDuck). Now enhance it with the following libraries and databases. Add each one with its import, a minimal working integration, and a comment explaining why it's there.

---

## ⚠️ IMPORTANT: How AI Studio Build Works
- You generate **working Python files** with correct imports
- Packages in `requirements.txt` are auto-installed
- SQLite is built into Python — no install needed
- External binaries (FFmpeg, Node.js) cannot be auto-installed — add graceful fallback checks
- Google Gemini API works natively in AI Studio (use `google-generativeai`)
- Streamlit is the UI framework — all UI must be Streamlit-compatible

---

## 📦 1. UPDATE `requirements.txt`

Add these lines to the existing requirements file:

```text
# ── Vector Database (semantic search for styles, prompts, characters) ──
chromadb>=0.5.0

# ── Audio (VO alignment, phoneme sync, foley timeline) ──
librosa>=0.10.0
soundfile>=0.12.0
pydub>=0.25.0
pyttsx3>=2.90
gTTS>=2.5

# ── Video (Light slideshow rendering) ──
ffmpeg-python>=0.2.0

# ── Text / NLP (Persian tokenization, semantic embeddings) ──
hazm>=3.0.0
sentence-transformers>=3.0.0

# ── Cache (agent output caching, thumbnail cache) ──
diskcache>=5.6

# ── Network (async HTTP for cloud uploads) ──
httpx>=0.27.0

# ── Animation (easing curves for camera movement) ──
easing-functions>=1.0.0

# ── AI (Google Gemini free tier, unified LLM interface) ──
google-generativeai>=0.7.0
litellm>=1.40.0

# ── Image (advanced pixel operations) ──
opencv-python-headless>=4.9.0
```

---

## 🗄️ 2. CREATE `tools/studio_db.py` — Database Layer

Create this file with:

### SQLite Database (`.story/studio.db`)
Tables:
```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'pending',
    brief TEXT,
    quality TEXT DEFAULT 'light',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    name TEXT,
    layers_json TEXT,  -- JSON: {"body": "path.png", "head": "path.png", "hand": "path.png"}
    rig_json TEXT,     -- JSON: {"pose": "idle", "expression": "neutral"}
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audio_catalog (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,     -- footstep, impact, whoosh, ambience, vocal
    file_path TEXT,
    duration_ms INTEGER,
    tags TEXT           -- comma-separated
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    brief TEXT,
    current_phase TEXT DEFAULT 'idle',
    quality TEXT DEFAULT 'light',
    duck_enabled INTEGER DEFAULT 1,
    messages_json TEXT, -- JSON array of chat messages
    updated_at TEXT DEFAULT (datetime('now'))
);
```

Functions to implement:
- `init_db()` — creates tables if not exist
- `save_job(job_id, status, brief, quality)` / `get_job(job_id)` / `list_jobs()`
- `save_character(id, name, layers, rig)` / `get_character(id)` / `list_characters()`
- `save_audio_cue(id, name, category, path, duration, tags)` / `get_cues_by_category(category)`
- `save_chat_session(session_id, data)` / `get_chat_session(session_id)`

### ChromaDB Vector Store (`.story/vectors/`)
Collections:
- `styles` — embeddings of visual style descriptions → for style recommendation
- `prompts` — embeddings of prompt templates → for shot prompt retrieval
- `characters` — embeddings of character descriptions → for character similarity

Functions:
- `init_chroma()` — creates persistent client at `.story/vectors/`
- `index_styles(style_catalog_path)` — load `libraries/styles/` into ChromaDB
- `find_similar_styles(query_text, n=3)` — semantic style search
- `index_prompts(prompt_templates_path)` — load `libraries/prompts/` into ChromaDB  
- `find_similar_prompts(action_text, n=1)` — find best prompt template for a shot
- `index_characters()` — load characters from SQLite into ChromaDB
- `find_similar_characters(description, n=3)` — semantic character search

### diskcache (`.story/cache/`)
- `cache_agent_output(brief_hash, phase, data)` — cache agent results
- `get_cached_agent_output(brief_hash, phase)` — retrieve cached result (returns None if expired)
- `cache_thumbnail(shot_id, image_bytes)` — cache generated thumbnails
- `get_cached_thumbnail(shot_id)` — retrieve cached thumbnail

---

## 🎵 3. CREATE `tools/studio_audio.py` — Audio Processing

### VO Duration Detection (using librosa)
```python
import librosa
import soundfile as sf

def get_audio_duration_frames(wav_path: str, fps: int = 24) -> int:
    """Return duration in frames (24fps) for a WAV file."""
    y, sr = librosa.load(wav_path, sr=None)
    duration_sec = len(y) / sr
    return max(1, round(duration_sec * fps))

def get_audio_info(wav_path: str) -> dict:
    """Return {duration_sec, sample_rate, channels, peak_amplitude}."""
    y, sr = librosa.load(wav_path, sr=None)
    return {
        "duration_sec": len(y) / sr,
        "sample_rate": sr,
        "channels": 1 if y.ndim == 1 else y.shape[0],
        "peak_amplitude": float(abs(y).max()),
    }
```

### TTS (Text-to-Speech for VO generation)
```python
def generate_vo_pyttsx3(text: str, output_path: str, voice_id: int = 0) -> str:
    """Offline TTS using Windows SAPI5. Returns path to WAV file."""
    import pyttsx3
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    if voices and voice_id < len(voices):
        engine.setProperty('voice', voices[voice_id].id)
    engine.setProperty('rate', 150)  # Speed
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    return output_path

def generate_vo_gtts(text: str, output_path: str, lang: str = 'fa') -> str:
    """Online TTS using Google TTS. Better quality, supports Persian."""
    from gtts import gTTS
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)
    return output_path

def generate_vo_smart(text: str, output_path: str, prefer_offline: bool = True) -> str:
    """Try offline first, fallback to online."""
    try:
        return generate_vo_pyttsx3(text, output_path)
    except Exception:
        try:
            return generate_vo_gtts(text, output_path)
        except Exception:
            raise RuntimeError("No TTS engine available")
```

### Audio Timeline Builder (using pydub)
```python
from pydub import AudioSegment

def build_foley_timeline(cues: list[dict], output_path: str, fps: int = 24) -> str:
    """
    Assemble audio timeline from cue events.
    cues: [{"file": "footstep.wav", "start_frame": 48, "volume_db": -3}, ...]
    Returns path to mixed WAV file.
    """
    # Calculate total duration from last cue
    max_frame = max((c["start_frame"] + 24 for c in cues), default=24)
    total_ms = int((max_frame / fps) * 1000)
    
    # Create silent base
    timeline = AudioSegment.silent(duration=total_ms)
    
    for cue in cues:
        sfx = AudioSegment.from_wav(cue["file"])
        if "volume_db" in cue:
            sfx = sfx + cue["volume_db"]  # Adjust volume
        start_ms = int((cue["start_frame"] / fps) * 1000)
        timeline = timeline.overlay(sfx, position=start_ms)
    
    timeline.export(output_path, format="wav")
    return output_path
```

---

## 🎬 4. CREATE `tools/studio_video.py` — Video Processing

### FFmpeg Slideshow Builder
```python
import ffmpeg
from pathlib import Path

def build_slideshow_ffmpeg(
    shots: list[dict],
    output_path: str,
    *,
    fps: int = 24,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """
    Build a simple slideshow MP4 from shot descriptions.
    Each shot = solid color background + text overlay.
    This is the Light quality render path.
    """
    import subprocess, tempfile, os
    
    # Build concat file for FFmpeg
    concat_lines = []
    for i, sh in enumerate(shots):
        dur = float(sh.get("duration_sec", 3.0))
        title = sh.get("title", f"Shot {i}")
        action = sh.get("action", "")
        
        # Create a simple frame image per shot using Pillow
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (width, height), color=(20, 30, 40))
        draw = ImageDraw.Draw(img)
        draw.text((100, height//2 - 40), title, fill=(255, 255, 255))
        draw.text((100, height//2 + 20), action[:100], fill=(200, 200, 200))
        
        frame_path = Path(tempfile.gettempdir()) / f"shot_{i:04d}.png"
        img.save(frame_path)
        
        concat_lines.append(f"file '{frame_path}'")
        concat_lines.append(f"duration {dur}")
    
    # Add last frame again (FFmpeg concat requirement)
    concat_lines.append(f"file '{concat_lines[-2].split(chr(39))[1]}'")
    
    concat_file = Path(tempfile.gettempdir()) / "concat.txt"
    concat_file.write_text("\n".join(concat_lines))
    
    # Run FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-vsync", "vfr",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")
    
    return output_path

def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is on PATH. Return False gracefully."""
    import shutil
    return shutil.which("ffmpeg") is not None
```

---

## 📝 5. CREATE `tools/studio_nlp.py` — Persian NLP & Embeddings

### Persian Text Processing
```python
def process_persian_brief(brief: str) -> dict:
    """
    Analyze Persian brief text.
    Returns {paragraphs, keywords, detected_beats, emotions}
    """
    try:
        from hazm import Normalizer, word_tokenize, POSTagger
        normalizer = Normalizer()
        normalized = normalizer.normalize(brief)
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in normalized.split('\n') if p.strip()]
        
        # Extract keywords (simple approach)
        tokens = word_tokenize(normalized)
        
        # Detect emotions
        emotion_words = {
            'شوک': 'shock', 'نگران': 'worry', 'خوشحال': 'happy',
            'غمگین': 'sad', 'عصبانی': 'angry', 'متعجب': 'surprised',
            'آرام': 'calm', 'ترس': 'fear', 'عشق': 'love',
        }
        found_emotions = [e for w, e in emotion_words.items() if w in normalized]
        
        return {
            'paragraphs': paragraphs,
            'word_count': len(tokens),
            'detected_emotions': list(set(found_emotions)),
        }
    except ImportError:
        # Fallback without hazm
        paragraphs = [p.strip() for p in brief.split('\n') if p.strip()]
        return {
            'paragraphs': paragraphs,
            'word_count': len(brief.split()),
            'detected_emotions': [],
        }
```

### Semantic Embeddings (for ChromaDB)
```python
def get_embedding_model():
    """Load multilingual embedding model (cached)."""
    from sentence_transformers import SentenceTransformer
    # paraphrase-multilingual-MiniLM-L12-v2 supports Persian + English
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

def embed_text(text: str) -> list[float]:
    """Convert text to 384-dim embedding vector."""
    model = get_embedding_model()
    return model.encode(text).tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    """Convert batch of texts to embeddings."""
    model = get_embedding_model()
    return model.encode(texts).tolist()
```

---

## 🤖 6. CREATE `tools/studio_llm.py` — LLM Integration

### Unified LLM Interface (using LiteLLM + Gemini)
```python
def get_llm():
    """
    Return the best available LLM client.
    Priority: Gemini (free) → OpenAI (if key set) → None (deterministic only)
    """
    import os
    
    # Try Gemini first (free tier, works in AI Studio)
    try:
        import google.generativeai as genai
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if key:
            genai.configure(api_key=key)
            return {"provider": "gemini", "model": "gemini-1.5-flash"}
    except ImportError:
        pass
    
    # Try OpenAI
    if os.getenv("OPENAI_API_KEY"):
        return {"provider": "openai", "model": "gpt-4o-mini"}
    
    return None

def enrich_with_llm(prompt: str, system: str = "") -> str | None:
    """
    Optional LLM enrichment. Returns None if no LLM available.
    Used to improve agent outputs when --use-llm flag is set.
    """
    llm = get_llm()
    if llm is None:
        return None
    
    if llm["provider"] == "gemini":
        import google.generativeai as genai
        model = genai.GenerativeModel(llm["model"])
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text
    
    if llm["provider"] == "openai":
        from openai import OpenAI
        client = OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=llm["model"],
            messages=messages,
        )
        return response.choices[0].message.content
    
    return None

def enrich_screenplay_with_llm(screenplay_md: str) -> str:
    """Use LLM to improve screenplay descriptions (more vivid, better pacing)."""
    return enrich_with_llm(
        prompt=f"Improve this animation screenplay. Make descriptions more vivid and visual. Keep the same structure:\n\n{screenplay_md}",
        system="You are a professional animation screenwriter. Write in Persian (Farsi). Use visual, cinematic language.",
    ) or screenplay_md

def enrich_style_recommendation_with_llm(brief: str, beat_list: str) -> str:
    """Use LLM to recommend visual style based on story content."""
    return enrich_with_llm(
        prompt=f"Story: {brief}\nBeats: {beat_list}\n\nRecommend a visual style (colors, lighting, mood) for this animation. Be specific.",
        system="You are a visual style consultant for 2D animation. Recommend color palettes, lighting styles, and mood.",
    )
```

---

## 🎯 7. UPDATE `agents/style_recommender_agent.py` — Use ChromaDB + Embeddings

Add this to the existing style recommender:

```python
def recommend_style_semantic(brief: str) -> dict:
    """
    Use ChromaDB + sentence-transformers to find the best matching style.
    Falls back to rule-based if vector DB is empty.
    """
    try:
        from tools.studio_nlp import embed_text
        from tools.studio_db import find_similar_styles
        
        # Semantic search
        results = find_similar_styles(brief, n=1)
        if results:
            return results[0]
    except Exception:
        pass
    
    # Fallback: keyword-based
    return recommend_style_keyword(brief)
```

---

## 🎬 8. UPDATE `agents/render_agent.py` — Add FFmpeg Graceful Fallback

Add this check at the start of render functions:

```python
def _check_render_readiness(quality: str) -> dict:
    """Check which render backends are available. Graceful fallback."""
    import shutil
    
    readiness = {
        "remotion_available": False,
        "ffmpeg_available": False,
        "recommended_mode": "code_only",
    }
    
    # Check Remotion
    remotion_dir = Path(__file__).resolve().parents[1] / "remotion"
    if (remotion_dir / "node_modules" / "remotion").is_dir():
        readiness["remotion_available"] = True
    
    # Check FFmpeg
    if shutil.which("ffmpeg"):
        readiness["ffmpeg_available"] = True
    
    # Recommend mode
    if quality == "pro" and readiness["remotion_available"]:
        readiness["recommended_mode"] = "direct_render"
    elif readiness["ffmpeg_available"]:
        readiness["recommended_mode"] = "direct_render"
    else:
        readiness["recommended_mode"] = "code_only"
    
    return readiness
```

---

## 🎨 9. UPDATE `app.py` — Add Readiness Indicator

Add a status badge in the UI sidebar showing which backends are available:

```python
def render_readiness_badge():
    """Show colored badges for available backends."""
    import shutil
    from pathlib import Path
    
    rem_ok = (Path(__file__).resolve().parent / "remotion" / "node_modules" / "remotion").is_dir()
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    gemini_ok = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    
    cols = st.columns(4)
    with cols[0]:
        st.caption(f"{'🟢' if rem_ok else '🔴'} Remotion")
    with cols[1]:
        st.caption(f"{'🟢' if ffmpeg_ok else '🔴'} FFmpeg")
    with cols[2]:
        st.caption(f"{'🟢' if gemini_ok else '⚪'} Gemini")
    with cols[3]:
        st.caption("🟢 SQLite")
```

Add `render_readiness_badge()` call at the top of `main()`.

---

## 🚀 10. CREATE `tools/studio_cache.py` — Caching Layer

```python
"""
Agent output caching using diskcache.
Avoids re-running expensive operations when the same brief is processed.
"""

import hashlib
from pathlib import Path
import diskcache

CACHE_DIR = Path(__file__).resolve().parents[1] / ".story" / "cache"

_cache = None

def _get_cache():
    global _cache
    if _cache is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache = diskcache.Cache(str(CACHE_DIR))
    return _cache

def brief_hash(brief: str) -> str:
    """Deterministic hash of brief text."""
    return hashlib.sha256(brief.encode()).hexdigest()[:16]

def cache_agent_output(brief: str, phase: str, data: dict) -> None:
    """Cache agent phase output. Auto-expires after 1 hour."""
    cache = _get_cache()
    key = f"{brief_hash(brief)}:{phase}"
    cache.set(key, data, expire=3600)

def get_cached_agent_output(brief: str, phase: str) -> dict | None:
    """Retrieve cached output. Returns None if not cached or expired."""
    cache = _get_cache()
    key = f"{brief_hash(brief)}:{phase}"
    return cache.get(key)

def cache_thumbnail(shot_id: int, image_bytes: bytes) -> None:
    """Cache a generated thumbnail image."""
    cache = _get_cache()
    cache.set(f"thumb:{shot_id}", image_bytes, expire=86400)

def get_cached_thumbnail(shot_id: int) -> bytes | None:
    """Retrieve cached thumbnail."""
    cache = _get_cache()
    return cache.get(f"thumb:{shot_id}")

def clear_cache() -> None:
    """Clear all cached data."""
    cache = _get_cache()
    cache.clear()
```

---

## 📋 IMPLEMENTATION ORDER

Build these files in this order:

1. **`requirements.txt`** — Add all new packages (copy from section 1 above)
2. **`tools/studio_db.py`** — SQLite + ChromaDB + diskcache (copy from section 2)
3. **`tools/studio_cache.py`** — Agent output caching (copy from section 10)
4. **`tools/studio_nlp.py`** — Persian NLP + embeddings (copy from section 5)
5. **`tools/studio_llm.py`** — Gemini integration (copy from section 6)
6. **`tools/studio_audio.py`** — VO + TTS + foley (copy from section 3)
7. **`tools/studio_video.py`** — FFmpeg slideshow (copy from section 4)
8. **Update `agents/style_recommender_agent.py`** — Add semantic search (section 7)
9. **Update `agents/render_agent.py`** — Add readiness check (section 8)
10. **Update `app.py`** — Add readiness badge + import cache/audio/llm (section 9)

---

## ✅ VERIFICATION CHECKLIST

After adding all libraries, verify:
- [ ] `from tools.studio_db import init_db, find_similar_styles` — no import error
- [ ] `from tools.studio_audio import generate_vo_smart, get_audio_duration_frames` — no import error
- [ ] `from tools.studio_video import check_ffmpeg_available` — returns True/False gracefully
- [ ] `from tools.studio_nlp import process_persian_brief` — works with Persian text
- [ ] `from tools.studio_llm import enrich_with_llm` — returns None gracefully if no API key
- [ ] `from tools.studio_cache import cache_agent_output` — writes to `.story/cache/`
- [ ] Streamlit UI shows readiness badges (green/red dots)
- [ ] All existing 181 tests still pass
- [ ] `python __main__.py export --brief "test" --quality light` works end-to-end