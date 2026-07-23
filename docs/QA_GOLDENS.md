# QA / smoke (Story)

Fixture: `fixtures/golden/story_light_beats/` (+ `expected/hashes.json`)

```powershell
$env:ANIMATION_DETERMINISTIC_SLIDES=1
python -m pytest tests -q
python scripts\smoke_render.py
python scripts\smoke_remotion.py
```

Refresh goldens:

```powershell
$env:ANIMATION_DETERMINISTIC_SLIDES=1
$env:UPDATE_GOLDENS=1
python -m pytest tests/test_story_golden.py -q
```

معیار قبول: pixel hash + Light/Pro MP4؛ long-form Light با `>12` شات → `backend=light_slideshow_concat`.
