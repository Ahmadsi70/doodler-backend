# Roadmap execution log

Ordered sprint (2026-07-19):

1. CI — `.github/workflows/ci.yml` (pytest + FFmpeg smoke + Pro props golden)
2. Golden Pro — `fixtures/golden/story_pro_props` (props contract)
3. SceneIR — `tools/scene_ir_builder.py` → `scene_ir.json` per job
4. Remotion ← craft — `craftHints` from Williams `shot_behaviors`
5. Visual enrichment — crossfade + parallax depth in `StoryNarrative.tsx`
6. Williams portable — `WILLIAMS_RULES_PATH` + `tools/williams_paths.py`
7. LLM schema validate — `agents/llm_enrich.py` validators
8. Supervisor multi-hop — `max_revision_passes` (default 2)
9. Scaffold quarantine — `tools/QUARANTINE.md`
10. LICENSE (MIT) · semver `0.2.0` · `Dockerfile` (Light)

## Pro visual v2 (done)

- `envProfile` multiplane environment per beat
- overlapping crossfade + slide transitions (`CROSSFADE_FRAMES=12`)
- `shotRig` + `craftHints.rig.pose/expression` → CharacterRig

## Architecture P0/P1 (2026-07-20)

See `docs/ARCHITECTURE_P0.md`.

- Act plan + CompressedContextPack wire-up
- Performance Bible → multi-phase `shotRig`
- Continuity graph on props
- Remotion visualVersion 3 (lower-third, cameraMove, transitionIn)
- Craft pack stubs: cine / look / transition / audio
- Golden: `fixtures/golden/story_props_contract/`

## Git hygiene

`C:\Users\badri\Story` must be its **own** git root (not nested under the user home repo).

```powershell
cd C:\Users\badri\Story
git init
git add .
git status
# commit when ready
```

Helper: `python -c "from tools.story_git import recommend_story_git_init; print(recommend_story_git_init('.'))"`

