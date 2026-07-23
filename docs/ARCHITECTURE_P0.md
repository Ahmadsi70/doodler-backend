# Architecture P0/P1 — Act scope + craft packs

## Source of truth

`StudioSpec` → compile / agents (optional) → `story_props.json` → Remotion.

SceneIR is an audit/bridge artifact (`scene_ir.json`); Remotion reads **props**, not IR.

## P0 modules

| Module | Path | Role |
|--------|------|------|
| Act plan | `tools/act_planner.py` | Split long films into contiguous acts |
| Context pack | `tools/context_pack.py` | Fill `SceneIR.compressed_context` (8–32K act scope) |
| Performance Bible | `libraries/performance/bible.json` | Walk/react/run cycles → `shotRig` |
| Continuity graph | `tools/continuity_graph.py` | Nodes/edges in `continuity.graph` |
| Cinematic props v3 | `tools/remotion_emitter.py` | `captionMode`, `cameraMove`, `transitionIn` |
| Remotion stage | `remotion/src/StoryNarrative.tsx` | Lower-third captions + move/transition |

## P1 pack stubs (executable JSON)

| Pack | Path |
|------|------|
| Cine lexicon | `libraries/cine/lexicon.json` |
| Look bible | `libraries/look/bible.json` |
| Transition grammar | `libraries/transitions/grammar.json` |
| Audio cues | `libraries/audio/cues.json` (files optional) |

Loader: `tools/craft_packs.py`.

## Props contract (visualVersion ≥ 3)

Each shot must expose: `shotRig`, `envProfile`, `craftHints`, `captionMode`, `cameraMove`, `transitionIn`.  
Continuity must include `graph` when available.

Golden check: `tests/test_p0_architecture.py`.

## Long-form render

```python
from tools.act_planner import plan_acts, chunk_spec_by_acts
from tools.act_render import render_spec_by_acts

chunks = chunk_spec_by_acts(spec, plan_acts(spec))
# or end-to-end:
render_spec_by_acts(spec, workspace="out/job", target_act_seconds=150)
```

CLI: `python __main__.py approve-render --job out\design1 --render --by-acts`

UI: Director Board step 3 → checkbox «رندر اکت‌به‌اکت + چسباندن»

## Film quality priorities (2026-07-20)

| Item | Status |
|------|--------|
| Look per-shot (`shot.look.palette`) | done |
| Cine shot_size + pan_follow/reveal_drift | done |
| Richer procedural audio + `import_cue_wav` | done |
| Performance bible blink metadata | done |
| UI layer uploads body/head/hand | done |
| Context pack → LLM storyboard hop | done |
| Continuity gate (`CONTINUITY_GATE_STRICT=1`) | done |
| PerformanceChart + ContactLock + contact audio | done |
| LocomotionCycle + CameraCurve + FrameGate | done |
| TransitionEdge + Foley + Compliance + ActingLead | done |
| PhonemeSync (dialogue → viseme lead ≤2f) | done |
| SceneIR ← frame artifacts (contacts/phonemes/chart) | done |
| VO wav + phoneme stretch + audioTimeline role=vo | done |
| Director Board supervision table (gates) | done |
| Story dedicated git root + gitignore | done |
| UI password (`STORY_UI_PASSWORD`) + Colab notebook | done |
| A: VO energy/Whisper align | done |
| B: GitHub docs + local CI plan (`docs/GITHUB.md`) | done (remote needs `gh`) |
| C: Board dialogue/vo/phoneme UI | done |
| D: Blink + depth + grain/LUT Remotion | done |

Replace audio stubs:

```powershell
python -c "from tools.audio_cues import import_cue_wav; import_cue_wav('foley_footstep', r'C:\path\step.wav')"
```
