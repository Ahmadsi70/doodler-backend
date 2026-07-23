# Audio library + AudioCueAgent

## Source

- **Kenney Impact Sounds** — [kenney.nl/assets/impact-sounds](https://kenney.nl/assets/impact-sounds)
- License: **CC0 1.0**
- Imported: **100** WAV files under `libraries/audio/files/`
- Catalog: `libraries/audio/catalog.json`
- Attribution: `libraries/audio/ATTRIBUTION.md`
- **Narrative stubs** (procedural): `vocal_laugh`, `vocal_giggle`, `whoosh_move`, `prop_pickup`, `cloth_rustle`, `magic_sparkle` — replace with CC0 via `import_cue_wav`

Re-import Kenney:

```powershell
python scripts/import_kenney_audio.py
```

## Naming

```text
foley_footstep_<material>_<nn>.wav
foley_hit_soft_<weight>_<nn>.wav
foley_hit_wood_<weight>_<nn>.wav
foley_hit_metal_<weight>_<nn>.wav
foley_hit_punch_<weight>_<nn>.wav
foley_land_<nn>.wav
vocal_laugh.wav / whoosh_move.wav / prop_pickup.wav   # narrative stubs
```

Legacy aliases (`foley_footstep`, `foley_hit_soft`, `stinger_reveal`) point at concrete files.

Beds (`ambience_*`) remain procedural stubs unless you replace them.

## Screenplay-synced SFX (P3)

1. `ScriptBreakdownAgent` (v2) → per-shot `sfx[]` with `cue_id` + `offset_frac` + `reason_fa` (FA/EN keywords)
2. Storyboard copies `sfx` → Literary/Screenplay lists **افکت صدا (SFX)** in markdown
3. `AudioCueAgent` prefers explicit `sfx` (reason=`screenplay_sfx@…`); else keyword pick
4. Remotion: `audioTimeline` → `<Audio>` in `StoryNarrative.tsx`

## AudioCueAgent

`agents/audio_cue_agent.py` selects **only** catalog `cue_id`s from shot beat + action keywords (Persian + English).

Wired in `tools/remotion_emitter.py` → `audioTimeline` → Remotion `<Audio>`.
