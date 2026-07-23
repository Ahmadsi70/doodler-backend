# ایجنت‌های Story

| Agent | Artifact | حالت v2 |
|-------|----------|---------|
| **DraftScreenplayAgent** | `draft_screenplay.json` | پیش‌نویس نمایشنامه از brief **قبل** از storyboard |
| **ScriptBreakdownAgent** | `script_breakdown.json` | beats، dialogue، **sfx[]**، shot list از پیش‌نویس (v2) |
| Storyboard | `agents/storyboard.json` | از breakdown (نه brief خام)؛ verb / phases / beat |
| Cinematography | `agents/cinematography.json` | beat-aware + Williams `shot_behaviors` |
| AnimationTiming | `agents/animation_timing.json` | defaults → Williams craft (همیشه re-apply بعد از LLM) |
| Continuity | `agents/continuity.json` | خط ۱۸۰° + look_space از cine |
| **AudioCueAgent** | `audio_cue_plan` → `audioTimeline` | فقط از کاتالوگ `libraries/audio/catalog.json`؛ با `contacts` به فریم تماس قفل می‌شود |
| **PerformanceChartAgent** | `performanceChart` → `shotRig` | چارت متراکم ۲۴fps (ant → action/extreme → hold) |
| **ContactLockAgent** | `contactLock` | فریم‌های `foot_L/R` / `impact` / `landing` (local + global) |
| **LocomotionCycleAgent** | `locomotionCycles` | چهارضرب: Contact→Down→Passing→Up |
| **CameraCurveAgent** | `cameraCurves` → `shot.cameraCurve` | کلید scale/tx با ease |
| **TransitionEdgeAgent** | `transitionEdges` → `transitionIn` | لبهٔ کات + safety continuity |
| **FrameGate** | `frameGate` (+ Supervisor) | تراکم keyframe / چهارضرب / تماس پا |
| **FoleyTimelineAgent** | `foleyTimeline` → audio | anticipation/brake/impact روی contact |
| **ComplianceFrameAgent** | `complianceFrame` | پرچم واقعی fps / ۱۸۰° / eyeline |
| **ActingLeadAgent** | `actingLead` → `expressionCurve` | چشم ۲–۴ فریم قبل از سر |
| **PhonemeSyncAgent** | `phonemeSync` → mouth curve | لب‌خوانی VO؛ visual ≤۲ف قبل از audio |
| **ScreenplayAgent** | `screenplay.json` + `screenplay.md` | نمایشنامه؛ با cine → **LiteraryScreenplayAgent** |
| **LiteraryScreenplayAgent** | `screenplay.md` (v2) | slugline، دوربین/نور، subtext، VO |
| **StyleRecommenderAgent** | `style_recommendation.json` | پیشنهاد style از brief + emotion |
| **DirectorNotesAgent** | `explanation.md` | توضیح زبان طبیعی هر شات قبل از رندر خارجی |
| **ImageNeedsAgent** | `image_needs` → `image_manifest.json` | نوع دارایی تصویر (keyframe / ref / establishing / insert) + framing 16:9 |
| **PromptCraftAgent** | `prompts/shot_XX.txt` + `assets/` + negative | پرامپت **فریم کلید / دارایی** grounded در فیلم‌نامه (v2) |
| Character library | `.story/characters/<id>/` | پروفایل سراسری portrait + appearance برای همه فیلم‌ها |
| **AnimationPromptAgent** | `shot_XX_motion.txt` + JSON + `tools/` | پرامپت **motion/I2V** (Runway/Kling/Pika) |
| **ExportBundleGate** | `export_gate.json` | QA بسته قبل از خروج از استودیو |
| StorySupervisor | `story_supervisor.json` | craft + pack gate + **یک hop اصلاح** |

ورودی پایپلاین: `run_brief_studio_graph` (LangGraph) یا `run_story_agent_chain_with_supervision`

**ترتیب craft (P0):**
1. `DraftScreenplayAgent` → `draft_screenplay.json`
2. `ScriptBreakdownAgent` → `script_breakdown.json`
3. `StyleRecommenderAgent` → `style_recommendation.json` (در craft)
4. `StoryboardAgent` → `storyboard.json` (از breakdown)
5. Cinematography → Timing → Continuity → Supervisor  
خروجی: **بستهٔ صدور** — رندر در Remotion/FFmpeg **خارج از Story**.  
مستندات گراف: `docs/STUDIO_GRAPH.md`

## صدور (export agents)
1. `ScreenplayAgent` → `screenplay.md` + `screenplay.json`
2. `DirectorNotesAgent` → `explanation.md`
3. `ImageNeedsAgent` → typed assets + framing (16:9 / crop / timeline_slot)
4. `PromptCraftAgent` → `prompts/` keyframes + `image_manifest.json` + `assets/`
5. `AnimationPromptAgent` → `prompts/*_motion.txt` + tool variants
6. `ExportBundleGate` → `export_gate.json` (fail-closed اگر فایل کم باشد)

## ارتقای v2
- پرامپت و خروجی deterministic هم‌ترازتر (schema `#v2`)
- بعد از LLM: `williams_craft=reapply`
- اگر Supervisor رد کند: حداکثر یک `revision=<Agent>` سپس ارزیابی مجدد

## P0 frame-level (۲۴fps ≈ ۴۱٫۷ms)
1. `PerformanceChartAgent` → `performanceChart#v1` + override `shotRig.keyframes`
2. `ContactLockAgent` → `contactLock#v1` از روی چارت
3. `AudioCueAgent(contacts=…)` → oneshot روی فریم تماس (±۰)
4. Emitter: `write_story_composition_props` این سه را در `story_props.json` می‌نویسد

## P1 frame-level
1. `LocomotionCycleAgent` → enrich چارت با فازهای چهارضرب
2. `CameraCurveAgent` → `cameraCurve` per shot؛ Remotion با ease نمونه‌برداری می‌کند
3. `FrameGate` → چک تراکم؛ `FRAME_GATE_STRICT=1` fail-closed؛ Supervisor اگر `performanceChart` در extras باشد می‌خواند
4. `TransitionEdgeAgent` → لبهٔ کات clamped + بدون slide روی risk

## P2 frame-level
1. `FoleyTimelineAgent` → ant/brake/impact روی contact؛ merge به `audioTimeline`
2. `ComplianceFrameAgent` → `fps_ok` / `line_180_ok` / `eyeline_ok` / chart
3. `ActingLeadAgent` → `expressionCurve` (چشم قبل از سر)

## P3 frame-level (VO)
1. `PhonemeSyncAgent` — از `ShotControl.dialogue` / نقل‌قول در action
2. `visual_frame ≤ audio_frame` با lead ۱–۲ فریم (قرارداد SceneIR)
3. Merge دهان به `expressionCurve`؛ بدون dialogue → `active=false`
