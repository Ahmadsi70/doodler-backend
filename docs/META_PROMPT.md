# Story Studio — Full Project Specification for Google AI Studio App Builder

You are building **Story Studio**, a professional 2D animation pre-production and rendering studio. The user writes a story brief in Persian (Farsi) or English, and a pipeline of AI agents generates a complete animation package — screenplay, storyboard, cinematography, timing, prompts, engine code, and optionally a rendered MP4 video.

## Tech Stack
- **Language**: Python 3.11+
- **UI**: Streamlit (wide layout, luxury editorial theme)
- **Orchestration**: LangGraph (StateGraph with checkpointing, falls back to imperative loop)
- **Video Engine**: Remotion (React-based, Node.js) for Pro quality, FFmpeg for Light slideshow
- **Data Models**: Pydantic v2 (`StudioSpec`, `ShotControl`)
- **Animation Principles**: Williams 12 Principles of Animation (24fps universal constant)

---

## 1. DATA MODELS (`studio_spec.py`)

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class ShotControl(BaseModel):
    title: str = ""
    action: str = ""  # What happens in the shot
    duration_sec: float = 3.0
    lens: str = "standard"  # standard | beauty | action | wide
    camera: str = "static"  # static | motivated_push | pan | tilt | track
    shot_size: str = "MS"  # CU | MCU | MS | MLS | LS | ELS
    composition: str = "C"  # L | C | R (rule of thirds)
    pose: str = "idle"  # idle | walk | react | run | jump
    expression: str = "neutral"
    story_beat: str = ""  # entrance | exit | reaction | reveal | conflict | decision | quiet_hold
    anticipation_frames: int = 6
    hold_frames: int = 12
    lighting: str = "three_point"
    look_space: str = "right"
    dialogue: str = ""
    vo_path: str = ""
    sfx: list[str] = []

class StudioSpec(BaseModel):
    title: str = "Story"
    quality: str = "light"  # light | pro
    mode: str = "direct"  # direct | agents
    runtime_seconds: float = 60.0
    use_agents: bool = True
    use_llm: bool = False
    character_path: Optional[str] = None
    style_id: str = "symmetrical_pastel_cinema"
    emotion: str = "neutral"
    max_revision_passes: int = 2
    shots: list[ShotControl] = []
```

---

## 2. AGENT PIPELINE (agents/ directory)

All agents are **deterministic rule-based functions** with optional LLM enrichment. Each agent takes structured input and returns structured output. Agents run in sequence orchestrated by LangGraph.

### Phase A — Screenplay Draft
**`agents/draft_screenplay_agent.py`** — `DraftScreenplayAgent`
- Input: narrative brief (paragraphs separated by blank lines)
- Output: `{"screenplay_md": "...", "scenes": [{"index": 0, "title": "...", "body": "...", "story_beat": "entrance"}], "scene_count": 3}`
- Splits brief into chapters, infers story beats from Persian/English keywords
- Keywords for beat inference:
  - entrance: "وارد", "enter", "arrive", "opens"
  - exit: "خارج", "exit", "leave", "depart"
  - reaction: "شوک", "shock", "react", "surprised"
  - reveal: "کشف", "reveal", "discover", "finds"
  - conflict: "درگیری", "fight", "conflict"
  - decision: "تصمیم", "decide", "chooses"
  - quiet_hold: "آرام", "quiet", "still", "pause"

### Phase B1 — Script Breakdown
**`agents/script_breakdown_agent.py`** — `ScriptBreakdownAgent`
- Input: screenplay scenes
- Output: structured shot list with `{shot_id, title, action, story_beat, dialogue, sfx, duration_sec, narrative_question, focal_point, composition_shape, action_phases, pose, expression}`

### Phase B2 — Style Recommendation
**`agents/style_recommender_agent.py`** — `StyleRecommenderAgent`
- Recommends visual style (pastel_muted, moody_teal_orange, clean_corporate, vivid_pop) based on brief content and emotion keyword detection

### Phase B3 — Storyboard
**`agents/story_chain.py`** (Storyboard section)
- Enriches each shot with: narrative_question, verb detection, composition_shape, action_phases (anticipation / action / aftermath), pose, expression
- Applies Williams craft pack behaviors per story beat

### Phase B4 — Cinematography
**`agents/story_chain.py`** (Cinematography section)
- Beat-aware camera/lens/look-space assignment
- Camera mapping: entrance→static, exit→static, reaction→motivated_push, reveal→static, conflict→motivated_push, decision→static
- Lens mapping: entrance→standard, reaction→action, reveal→beauty, quiet_hold→beauty, conflict→action

### Phase B5 — Animation Timing
**`agents/story_chain.py`** (Timing section)
- Per-shot frame timing with anticipation, action, and hold phases
- 24fps universal constant
- Williams timing recipes: action_bias (even | slow_in | slow_out)

### Phase B6 — Continuity
**`agents/story_chain.py`** (Continuity section)
- 180-degree rule enforcement
- Screen direction consistency (L→R or R→L)
- Eyeline consistency
- Cause-before-effect causality checks

### Phase C — Supervisor
**`agents/story_supervisor.py`** — `StorySupervisor`
- Scores craft output: beat count, causality, character presence, continuity violations
- If score < threshold, sets `revision_target` and triggers revise loop (max 2-3 passes)

### Phase D — Export Agents
**`agents/screenplay_agent.py`**: Final `screenplay.md` + `screenplay.json`
**`agents/literary_screenplay_agent.py`**: Enhanced screenplay with sluglines, camera notes, subtext
**`agents/director_notes_agent.py`**: Natural language explanation per shot
**`agents/image_needs_agent.py`**: Image asset requirements (keyframe/ref/establishing)
**`agents/prompt_craft_agent.py`**: Diffusion model prompts per shot (`prompts/shot_XX.txt`)
**`agents/animation_prompt_agent.py`**: Motion/I2V prompts for Runway, Kling, Pika
**`agents/export_bundle_gate.py`**: QA gate before bundle exits studio

### Phase E — Render Agent
**`agents/render_agent.py`** — `RenderAgent`
- Two modes: `code_only` (generates ready-to-run scripts) or `direct_render` (invokes engine)
- Pro quality → Remotion (Node.js): `npx remotion render StoryNarrative render.mp4 --props story_props.json`
- Light quality → FFmpeg slideshow
- Generates: `render.ps1`, `render.sh`, `RENDER_README.md` for code-only mode
- Returns: `{ok, backend, render_mp4, code_dir, code_files, run_command, error}`

---

## 3. FRAME-LEVEL AGENTS (P0-P3 priority)

These operate at 24fps per-frame granularity:

- **`agents/performance_chart_agent.py`**: Dense 24fps performance charts (anticipation → action/extreme → hold)
- **`agents/contact_lock_agent.py`**: Foot contact/impact/landing frame markers
- **`agents/locomotion_cycle_agent.py`**: Quadruped walk cycles (Contact→Down→Passing→Up)
- **`agents/camera_curve_agent.py`**: Camera scale/tx keyframes with ease curves
- **`agents/transition_edge_agent.py`**: Cut edges + safety continuity
- **`agents/foley_timeline_agent.py`**: Anticipation/brake/impact Foley on contact frames
- **`agents/compliance_frame_agent.py`**: FPS, 180° line, eyeline compliance checks
- **`agents/acting_lead_agent.py`**: Eye expression curves (eyes lead head by 2-4 frames)
- **`agents/phoneme_sync_agent.py`**: Lip-sync from VO/dialogue (visual ≤ 2 frames before audio)
- **`agents/audio_cue_agent.py`**: Audio cues from catalog, locked to contact frames

---

## 4. VIRTUAL RUBBER DUCK AGENT

**`agents/rubber_duck_agent.py`** — `RubberDuckAgent`

A meta-agent that questions every other agent's output. Not blocking — it suggests, the user decides.

### Data structures:
```python
@dataclass
class DuckQuestion:
    id: str
    phase: str  # screenplay | breakdown | storyboard | cinematography | timing | continuity
    severity: str  # critical | warning | suggestion | praise
    title_fa: str  # Short Persian title
    detail_fa: str  # Full explanation
    target_shot: int | None
    target_field: str | None
    suggested_fix: str | None
    suggested_value: Any | None
    rule_ref: str | None  # Williams principle or QC rule reference
    needs_user_decision: bool
```

### Interrogation methods (each returns `list[DuckQuestion]`):

**`interrogate_screenplay(screenplay)`**:
- Scene count check (0→critical, 1→suggestion)
- Abrupt transition detection (entrance→exit, conflict→quiet_hold)
- Missing emotion words in action descriptions

**`interrogate_breakdown(shots)`**:
- Multi-focus detection (>2 sentences in action → warning)
- Beat-action mismatch (keyword inference vs assigned beat)

**`interrogate_storyboard(shots)`**:
- Pose-beat alignment (expected pose per beat: entrance→walk, reaction→react, idle→quiet_hold, etc.)
- Duration vs dialogue length (estimate read time, flag if too short)
- Anticipation frames minimum per beat (entrance:4, reaction:6, reveal:8, conflict:8)
- Hold frames minimum (8 frames unless entrance/exit)
- Too-fast detection (Williams "major_beginner_mistake_too_fast": <24 frames with long action)

**`interrogate_cinematography(shots, cine_frames)`**:
- Camera-beat match against recommended camera per beat
- Lens-emotion match (beauty for emotional, action for conflict)

**`interrogate_continuity(shots, continuity)`**:
- 180° rule violation detection from continuity dict
- Screen direction flip detection
- Eyeline inconsistency detection

**`interrogate_timing(shots)`**:
- Action bias per beat (reaction→slow_in, conflict→slow_out, entrance→even)

**`interrogate_export(shots)`**:
- Zero-duration shot detection (critical)
- Rhythm praise when ≥3 shots with varied beats

### Persian message templates for every check (use these exact patterns):
All messages are in Persian (Farsi). Every question has: `title_fa` (short), `detail_fa` (full explanation with shot numbers and values), `suggested_fix` (concrete action).

### Duck controls:
- `muted` flag — can be silenced
- `strictness` levels: "silent" | "gentle" | "normal" | "strict"
- `summary_fa()` — one-line summary like "⚠ 2 بحرانی | 💡 5 پیشنهاد"

---

## 5. LANGGRAPH ORCHESTRATION (`tools/studio_graph.py`)

### State type (`tools/studio_job_state.py`):
```python
class StudioJobState(TypedDict, total=False):
    mode: str  # brief | spec
    brief: str
    job_dir: str
    extras: dict[str, Any]
    style_profile: dict[str, Any]
    targets: list[str]
    max_revision_passes: int
    revision_passes: int
    chain: dict[str, Any]  # StoryChainResult serialized
    screenplay: dict[str, Any]
    screenplay_approved: bool
    supervisor: dict[str, Any]
    spec: dict[str, Any]
    approved: bool
    bundle: dict[str, Any]
    gate: dict[str, Any]
    artifacts: dict[str, Any]
    ok: bool
    error: str
    phase: str
    logs: list[str]
    awaiting_approve: bool
    awaiting_screenplay: bool
    render_requested: bool
    render_mode: str
    render_result: dict[str, Any]
```

### Three graphs:

**1. Brief Craft Graph** (design only, for UI):
```
draft_screenplay → await_screenplay → [interrupt] → craft_visual → supervisor → [revise*] → complete → END
```
- Human gate at `await_screenplay` via LangGraph `interrupt()`
- Skip with `extras["skip_screenplay_gate"]=True`

**2. Brief Studio Graph** (full CLI pipeline):
```
craft_chain → supervisor → [revise → supervisor]* → export → gate → [render] → END
```
- Render node activates only when `extras["render"]=True`

**3. Spec Export Graph** (from pre-built StudioSpec):
```
await_approve → [interrupt] → export → gate → [render] → END
```

### Node functions:
- `_node_craft_chain(state)`: runs `run_story_agent_chain()` — full screenplay→breakdown→storyboard→cine→timing→continuity
- `_node_supervisor(state)`: runs `run_story_supervisor()`, returns score and revision_target
- `_node_revise(state)`: runs `revise_for_target()` for targeted revision
- `_node_export(state)`: runs `export_animation_bundle()`, generates screenplay + prompts + engine code
- `_node_gate(state)`: reads `export_gate.json`, checks bundle integrity
- `_node_render(state)`: runs `RenderAgent`, produces MP4 or render scripts
- `_route_after_gate(state)`: returns "render" if `extras["render"]` or `state["render_requested"]`, else "end"

### Fallback:
If LangGraph not installed, falls back to imperative loop in `_run_brief_fallback()` / `_run_spec_fallback()`.

---

## 6. EXPORT & RENDER TOOLS

### `tools/animation_export.py`
- `export_animation_bundle(spec, export_dir, targets)`: writes screenplay.md, prompts/, story_props.json, engines/
- Targets: "prompts", "remotion", "slideshow"
- Runs all Phase D export agents

### `tools/remotion_emitter.py`
- `write_story_composition_props(out_dir, storyboard, cinematography, timing, continuity, ...)`: writes `story_props.json` — the single source of truth for Remotion
- Shot props: shotId, title, action, durationSec, durationFrames, holdFrames, anticipationFrames, dialogue, voPath, lens, camera, cameraMove, shotSize, composition, lighting, thirdsX, lookSpace, verb, storyBeat, sfx, craftHints, envProfile, shotRig, transitionIn, expressionCurve, cameraCurve
- `render_remotion(out_dir)`: invokes `npx remotion render` subprocess → `render.mp4`
- `render_story(brief, out_dir, quality)`: Pro→Remotion, Light→FFmpeg slideshow
- Writes all frame-agent artifacts: performanceChart, contactLock, locomotionCycles, cameraCurves, transitionEdges, foleyTimeline, actingLead, phonemeSync, audioTimeline

### `tools/story_pipeline.py`
- `run_story_job(prompt, job_id, extras)`: main CLI entry point
- `readiness_probe()`: checks ffmpeg, remotion, node availability

---

## 7. WILLIAMS CRAFT PACK

### `tools/williams_craft.py`
- `load_williams_craft_pack()`: loads from `libraries/williams/` (principles.json, timing_recipes.json, shot_behaviors.json, anti_patterns.json)
- `infer_story_beat(action)`: keyword-based beat inference
- `behavior_for_beat(beat)`: returns Williams behavior for a story beat
- `apply_williams_craft(shots)`: applies timing recipes and anti-pattern detection

### Key Williams anti-patterns to detect:
- `major_beginner_mistake_too_fast`: duration_frames < 24 with complex action
- `midpoint_impact_squash`: squash before contact frame
- `straight_line_inbetweening`: no arcs in organic movement
- `level_pelvis_walk`: no up/down in walk cycle

---

## 8. STREAMLIT UI (`app.py`)

### Theme (luxury editorial):
- Primary color: `#9a7b4f` (antique brass)
- Background: `#f3efe6` (pearl stone)
- Text: `#14221f` (ink forest)
- Fonts: Figtree (sans-serif) + Spectral (serif) from Google Fonts

### Two modes, switchable via buttons at top:

**Mode 1 — 📋 Wizard (3-step classic)**:
- Step 0: Brief text area + advanced settings (character upload, quality, style, emotion, runtime)
- Step 1: Shot table preview + detail cards (edit shot, revise, craft explorer, download)
- Step 2: Approve & Export (approve button, export button, render options)
- Modal dialogs via `st.dialog` for: screenplay approval, shot editing, revise prompt, bundle preview, frame supervision

**Mode 2 — 💬 Director Chat (new conversational mode)**:
- Left panel (3/4 width): Chat message history with styled agent bubbles + input bar
- Right panel (1/4 width): Status panel showing current phase, shot table, duck status
- Message bubbles with color-coded left borders per agent:
  - DraftScreenplay: `#7eb8da` 📝
  - ScriptBreakdown: `#b8a0d0` 🔍
  - StoryboardAgent: `#8cc4a0` 🎬
  - CinematographyAgent: `#d4a870` 📷
  - RubberDuck: `#fef9e8` background, `#e8c030` border 🦆
- Chat input: multi-line text area + send button + quick suggestion chips
- Command parser for Persian/English: "تأیید", "شات ۲ دوربین static", "اردک ساکت", "رندر کن"
- Background threads for agent execution (screenplay generation, visual craft, export, render)
- Session persistence to `.story/chat_session.json`

### Chat Flow:
1. User enters brief → system shows "received"
2. Background: `run_brief_craft_graph(skip_screenplay_gate=True)` generates screenplay + storyboard
3. DraftScreenplay agent message appears in chat
4. RubberDuck interrogates screenplay → duck messages appear
5. StoryboardAgent message appears
6. RubberDuck interrogates storyboard → duck messages appear
7. User can: approve ("تأیید"), edit shots ("شات ۲ دوربین static"), ask duck ("اردک شات ۱ رو چک کن"), render ("رندر کن"), export code ("کد بده")
8. Export agent shows bundle path
9. Render agent produces MP4 or scripts

### Chat Command Parser (`tools/director_chat.py`):
```python
class CommandKind(Enum):
    BRIEF = "brief"        # Multi-paragraph story text
    APPROVE = "approve"    # تأیید, ok, yes, برو بعدی
    REJECT = "reject"      # نه, no, رد, برگرد
    EDIT_SHOT = "edit_shot"  # شات N فیلد مقدار
    REVISE = "revise"      # Free-form revise prompt
    ASK_DUCK = "ask_duck"  # اردک سوال
    MUTE_DUCK = "mute_duck"  # اردک ساکت
    UNMUTE_DUCK = "unmute_duck"  # اردک صحبت کن
    RENDER = "render"      # رندر کن
    EXPORT = "export"      # کد بده, صدور
    SKIP = "skip"          # بگذر
    RESET = "reset"        # شروع دوباره
```

Field name mappings (Persian→English): دوربین→camera, پوز→pose, لنز→lens, مدت→duration_sec, دیالوگ→dialogue, beat→story_beat, ترکیب→composition
Value normalization for camera (static/ثابت→static, push/هل→motivated_push), pose (ایستاده→idle, راه→walk, واکنش→react), composition (چپ→L, وسط→C, راست→R)

---

## 9. DIRECTORY STRUCTURE

```
Story/
├── app.py                    # Streamlit UI (wizard + chat)
├── story_cli.py              # CLI entry point
├── __main__.py               # python -m entry
├── studio_spec.py            # Pydantic data models
├── scene_ir.py               # Intermediate representation
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Project config
├── agents/
│   ├── story_chain.py        # Main agent chain orchestrator
│   ├── story_supervisor.py   # Quality supervisor
│   ├── draft_screenplay_agent.py
│   ├── script_breakdown_agent.py
│   ├── style_recommender_agent.py
│   ├── screenplay_agent.py
│   ├── literary_screenplay_agent.py
│   ├── director_notes_agent.py
│   ├── image_needs_agent.py
│   ├── prompt_craft_agent.py
│   ├── animation_prompt_agent.py
│   ├── render_agent.py       # Phase E render
│   ├── rubber_duck_agent.py  # Virtual Rubber Duck
│   ├── performance_chart_agent.py
│   ├── contact_lock_agent.py
│   ├── locomotion_cycle_agent.py
│   ├── camera_curve_agent.py
│   ├── transition_edge_agent.py
│   ├── foley_timeline_agent.py
│   ├── acting_lead_agent.py
│   ├── phoneme_sync_agent.py
│   ├── audio_cue_agent.py
│   ├── compliance_frame_agent.py
│   └── sfx_plan.py
├── tools/
│   ├── studio_graph.py       # LangGraph orchestration
│   ├── studio_job_state.py   # Graph state TypedDict
│   ├── studio_api.py         # Code-first API (export_from_spec, render_from_spec)
│   ├── story_pipeline.py     # CLI pipeline
│   ├── animation_export.py   # Export bundle builder
│   ├── remotion_emitter.py   # Remotion story_props.json + render
│   ├── director_board.py     # Design state management
│   ├── director_chat.py      # Chat session + command parser
│   ├── director_ui_chat.py   # Streamlit chat components
│   ├── director_ui_shell.py  # Panel constants + navigation
│   ├── director_ui_panels.py # Detail card renderers
│   ├── director_ui_data.py   # UI data layer
│   ├── frame_supervision_ui.py
│   ├── williams_craft.py     # Williams principles loader
│   ├── williams_bridge.py    # Node.js bridge
│   ├── continuity_graph.py   # Continuity graph builder
│   ├── craft_packs.py        # Camera/look/transition craft
│   ├── pose_presets.py       # Pose preset library
│   ├── character_library.py  # Character profiles
│   ├── style_catalog.py      # Visual style catalog
│   ├── audio_cues.py         # Audio cue manager
│   ├── vo_align.py           # Voice-over alignment
│   ├── cloud_pack.py         # Cloud render ZIP
│   ├── story_pack.py         # Shareable pack export
│   ├── act_planner.py        # Act structure planner
│   ├── chapter_tools.py      # Brief→chapter splitting
│   ├── job_workspace.py      # Job directory management
│   ├── frame_gate.py         # Frame density gate
│   ├── export_bundle_gate.py # Export integrity gate
│   └── scene_ir_builder.py   # SceneIR builder
├── libraries/
│   ├── williams/             # Williams animation principles JSON
│   │   ├── principles.json
│   │   ├── timing_recipes.json
│   │   ├── shot_behaviors.json
│   │   └── anti_patterns.json
│   ├── story/                # Quality checklist, style rules
│   ├── cine/                 # Cinematic lexicon
│   ├── look/                 # Visual look bible
│   ├── performance/          # Performance bible
│   ├── styles/               # Style catalog
│   ├── audio/                # Foley catalog + WAV files
│   └── prompts/              # Motion prompt templates
├── docs/                     # Documentation (AGENTS.md, DIRECTOR_BOARD.md, etc.)
├── remotion/                 # Remotion React project (npm)
│   ├── package.json
│   ├── src/
│   │   └── StoryNarrative.tsx  # Main Remotion composition
│   └── public/
│       └── story_props.json    # Props consumed by Remotion
└── tests/                    # pytest test suite
```

---

## 10. WILLIAMS ANIMATION PRINCIPLES INTEGRATION

The entire system is built around the 12 Principles of Animation at 24fps:

1. **Squash and Stretch**: Applied via `shotRig` deformation curves in Remotion
2. **Anticipation**: Every shot has `anticipation_frames` (minimum per beat: entrance 4, reaction 6, reveal 8, conflict 8)
3. **Staging**: Composition (L/C/R thirds), shot_size, camera angle
4. **Straight Ahead / Pose to Pose**: Performance chart with keyframes
5. **Follow Through / Overlapping Action**: Action phases (anticipation → action → aftermath)
6. **Slow In / Slow Out**: `action_bias` field (even | slow_in | slow_out) per beat
7. **Arcs**: Camera curves with ease functions
8. **Secondary Action**: Expression curves, eye leads head by 2-4 frames
9. **Timing**: 24fps universal, duration_frames, hold_frames
10. **Exaggeration**: Pose presets (idle/walk/react/run/jump) with intensity
11. **Solid Drawing**: Not applicable (2D puppet style)
12. **Appeal**: Character rig, expression, lighting, envProfile

---

## 11. KEY DESIGN PRINCIPLES

- **Deterministic agents first**, LLM enrichment optional (`--use-llm` flag)
- **Human-in-the-loop** via LangGraph interrupts at screenplay and design approval gates
- **Code-first control** — `StudioSpec` can be authored directly in Python/JSON, bypassing agents
- **No in-tool video rendering by default** — Phase E is opt-in via `--render` flag
- **Williams principles at 24fps** as universal constant
- **Persian-first UI** with bilingual command support
- **Pack/share model** — export portable packs for others to use

---

## 12. CLI COMMANDS

```bash
python __main__.py ready                                    # Readiness probe
python __main__.py export --brief "..." --quality pro       # Export bundle only
python __main__.py export --brief "..." --quality pro --render  # Export + render MP4
python __main__.py export --brief "..." --render --code-only    # Export + render scripts
python __main__.py export --spec examples/studio_spec.json  # From pre-built spec
python __main__.py render-only --export-dir out/job/export  # Render from existing export
python __main__.py render-only --spec examples/studio_spec.json --quality pro
python __main__.py design --brief "..." --out out/design1   # Director design (UI)
python __main__.py revise --job out/design1 --prompt "..."  # Revise design
streamlit run app.py                                        # Launch Director Board UI
```

---

## 13. TESTING

```bash
pytest tests/ -q                    # 180+ tests
python scripts/smoke_render.py      # End-to-end smoke test
```

Tests cover: screenplay generation, script breakdown, storyboard enrichment, cinematography assignment, animation timing, continuity checks, supervisor scoring, export bundle integrity, LangGraph graphs, render agent, rubber duck interrogations, command parser, chat session save/load.

---

## BUILD INSTRUCTIONS FOR AI STUDIO

Build this as a **single Python project** with the structure above. Start with the core data models (`studio_spec.py`), then implement agents one by one, then the orchestration layer, then the UI. The Remotion React project can be a simple template that reads `story_props.json` and renders each shot as a sequence with transitions.

**Priority order for implementation:**
1. `studio_spec.py` — data models
2. `agents/story_chain.py` — main agent pipeline
3. `tools/williams_craft.py` — Williams principles
4. `tools/studio_graph.py` — LangGraph orchestration
5. `tools/animation_export.py` + `tools/remotion_emitter.py` — export & render
6. `agents/rubber_duck_agent.py` — quality validation
7. `agents/render_agent.py` — Phase E render
8. `app.py` — Streamlit UI with wizard + chat
9. `tools/director_chat.py` + `tools/director_ui_chat.py` — chat system
10. Frame-level agents (P0-P3)
11. Remotion React template
12. Tests

Make it work. Make it right. Make it fast.