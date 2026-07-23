# Story روی Google Colab — صدور بسته (بدون رندر)

هدف: متن داستان → **نمایشنامه + پرامپت + کد** در Drive.  
ویدیو داخل Colab ساخته **نمی‌شود**.

## قدم‌به‌قدم

### Drive
```text
My Drive/Story/
  __main__.py
  requirements.txt
  tools/
```

### Colab
1. Upload `notebooks/story_colab.ipynb`
2. Run all · Allow Drive mount
3. Brief در سلول ۳ را عوض کن

### خروجی
```text
My Drive/StoryOut/<job_id>/
  screenplay.md
  explanation.md
  prompts/
  engines/slideshow/
  engines/remotion/   (props + guide)
```

## رندر ویدیو
خارج از Story — طبق `engines/*/guide.md` روی PC یا سرور خودت.

## لوکال (تخته کارگردان)
```powershell
cd C:\Users\badri\Story
streamlit run app.py
python __main__.py export --brief "..."
```
تخته کارگردان قبل از storyboard در **تأیید پیش‌نویس سناریو** متوقف می‌شود؛ CLI/Colab با `skip_screenplay_gate` یک‌مرحله‌ای می‌مانند. Checkpoint: `STORY_CHECKPOINT_DIR` (پیش‌فرض `.story/checkpoints/studio_graph.db`).
