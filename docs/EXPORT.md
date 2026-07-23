# صدور بستهٔ ساخت انیمیشن

Story دیگر **ویدیو داخل ابزار** نمی‌سازد. خروجی = نمایشنامه + توضیح + پرامپت + کد موتور مقصد.

## CLI

```powershell
python __main__.py export --brief "شات۱.`n`nشات۲." --quality pro
python __main__.py export --spec examples\studio_spec.json --out out\my_job
python __main__.py design --brief "..." --out out\design1
python __main__.py approve-render --job out\design1 --render
```

## ساختار بسته (`export/`)

| فایل | نقش |
|------|-----|
| `screenplay.md` | نمایشنامه و جدول شات |
| `explanation.md` | توضیح زبان طبیعی |
| `prompts/shot_XX.txt` | پرامپت فریم کلید (تصویر) |
| `prompts/shot_XX_motion.txt` | پرامپت motion/I2V |
| `prompts/tools/runway/` … | نسخهٔ Runway/Kling/Pika |
| `engines/remotion/` | `story_props.json` + راهنما |
| `engines/slideshow/` | `build.py` + راهنما |
| `studio_spec.json` | مشخصات فنی |

## تخته کارگردان

`streamlit run app.py` → Approve → **صدور بستهٔ ساخت**

رندر را خودتان با راهنمای داخل `engines/*/guide.md` اجرا کنید.

## بستهٔ کلود (ZIP)

بعد از طراحی یا صدور:
- دیالوگ **دانلود طراحی** → آماده‌سازی → **بستهٔ کلود Remotion (.zip)**
- یا در دیالوگ صدور → تب مسیر → **ساخت ZIP کلود**

محتوا: `remotion/` (scaffold) + `story_props.json` + کاراکتر + `CLOUD_RENDER.md`

```bash
unzip cloud_render_pack.zip
cd remotion && npm install
npx remotion render src/index.ts StoryNarrative out/film.mp4 --props=./story_props.json
```

مستند CLI: https://www.remotion.dev/docs/cli/render
