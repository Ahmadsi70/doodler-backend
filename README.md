# Story / Narrative (standalone 2D)

استودیوی **صدور دستور ساخت انیمیشن** — با قابلیت رندر مستقیم MP4 یا خروجی کد.  
Python agents + Williams timing → **نمایشنامه + پرامپت + کد موتور + MP4**.

## نصب

```powershell
cd C:\Users\badri\Story
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Remotion (برای رندر Pro): `cd remotion && npm install`
FFmpeg (برای رندر Light): نصب روی PATH

Williams: `npm run build` در پکیج rules · `WILLIAMS_RULES_PATH` در `.env`

Colab: `docs/COLAB.md` · `notebooks/story_colab.ipynb`  
صدور: `docs/EXPORT.md` · UI: `STORY_UI_PASSWORD`

## اجرا

```powershell
python __main__.py ready
```

### فقط صدور (کد + پرامپت)
```powershell
python __main__.py export --brief "شات۱.`n`nشات۲." --quality pro
python __main__.py export --spec examples\studio_spec.json --out out\my_job
```

### صدور + رندر مستقیم MP4 (Phase E)
```powershell
python __main__.py export --brief "..." --quality pro --render
python __main__.py export --spec examples\studio_spec.json --render
```

### صدور + کد آماده اجرا (بدون رندر خودکار)
```powershell
python __main__.py export --brief "..." --quality pro --render --code-only
```

### رندر از خروجی موجود (بدون اجرای مجدد ایجنت‌ها)
```powershell
python __main__.py render-only --export-dir out\my_job\export --quality pro
python __main__.py render-only --spec examples\studio_spec.json --quality light
```

### Director Board (UI)
```powershell
python __main__.py design --brief "..." --out out\design1
python __main__.py approve-render --job out\design1 --render
python __main__.py pack-export --spec examples\studio_spec.json --out packs\my_film
streamlit run app.py
```

## معماری

```
brief → agents → StudioSpec
     → export/: screenplay · explanation · prompts · engines/
     → Phase E: render_code/ (اسکریپت‌های قابل اجرا) یا render.mp4 (رندر مستقیم)
```

### گراف LangGraph:
```
craft → supervisor → [revise]* → export → gate → [render] → END
```

## تست

```powershell
$env:ANIMATION_DETERMINISTIC_SLIDES=1
python -m pytest tests -q
python scripts\smoke_render.py
```
