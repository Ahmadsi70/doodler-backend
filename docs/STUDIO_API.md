# Code-first Studio API

هدف: استودیوی آزاد که **همه‌چیز با کد/JSON** کنترل شود؛ ایجنت‌ها اختیاری‌اند.

## کنترل‌پلین

`StudioSpec` (`studio_spec.py`) → `tools/studio_api.py` → Remotion / Light

| فیلد شات | کنترل |
|----------|--------|
| `action` | متن روی شات |
| `duration_sec` | طول |
| `lens` / `camera` / `composition` | سینما |
| `pose` / `expression` | ریگ / عکس |
| `anticipation_frames` / `hold_frames` | زمان‌بندی ویلیامز |
| `story_beat` | محیط + craft |
| `character_path` | عکس کاربر |

## مثال JSON

```powershell
python __main__.py render --write-example-spec examples\studio_spec.json
python __main__.py render --spec examples\studio_spec.json --quality pro --character C:\path\hero.png
```

## مثال Python

```python
from studio_spec import ShotControl, StudioSpec
from tools.studio_api import render_from_spec

spec = StudioSpec(
    title="My Film",
    quality="pro",
    mode="direct",  # کد = منبع حقیقت
    character_path=r"C:\assets\hero.png",
    shots=[
        ShotControl(
            action="Hero enters.",
            duration_sec=3,
            pose="walk",
            story_beat="entrance",
            composition="L",
        ),
        ShotControl(
            action="Then shock because fire.",
            duration_sec=4,
            pose="react",
            expression="shock",
            camera="motivated_push",
            lens="action",
            story_beat="reaction",
            anticipation_frames=8,
            hold_frames=16,
        ),
    ],
)
print(render_from_spec(spec))
```

## حالت‌ها

- `mode=direct` (پیشنهادی): بدون حدس ایجنت؛ فقط Spec
- `mode=agents` + `use_llm=true`: ایجنت/LLM فقط متن را صیقل می‌دهد؛ دوربین/pose از Spec می‌ماند
