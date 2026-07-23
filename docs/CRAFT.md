# Craft (Story)

منبع: `libraries/story/style_rules.json` + `quality_checklist.json` + `anti_patterns.json` + `timing_rules.json`.

## Williams craft pack

دیتاست عملیاتی (نه کپی متن کتاب) در `libraries/williams/`:

| فایل | نقش |
|------|-----|
| `principles.json` | ۱۲ اصل عملیاتی |
| `timing_recipes.json` | دستور فریم ۲۴fps (+ backfill از `timing_rules`) |
| `shot_behaviors.json` | beat روایی → timing/camera/lens/rig |
| `anti_patterns.json` | خطای ویلیامز (جدا از `story/anti_patterns.json`) |
| `meta.json` | نسخه و provenance |

اعمال در زنجیره: `tools/williams_craft.py` → `run_animation_timing(..., cinematography=...)`.

زمان‌بندی Pro از **Williams TS** (`williams-animation-rules` → `remotion/scripts/enrich_timing.mjs`) هم می‌آید؛ رندر ویدیو با Remotion محلی است، نه Blender.
