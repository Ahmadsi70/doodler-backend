# Quarantined / disabled paths

These modules remain only as explicit stubs so old imports fail loudly:

| Path | Status |
|------|--------|
| `tools/manim_emitter.py` | Always raises — Manim disabled |
| `tools/path_c_fill.py` | Always raises — photo via CLI/UI only |
| `scripts/smoke_manim.py` | Exits 2 |
| `requirements-manim.txt` | Do not install for Story |

Use `quality=light` (FFmpeg) or `quality=pro` (Remotion local).
