# راهنمای کاربر — Story / Narrative

Brief روایی را در چند پاراگراف (با خط خالی) بنویس: شروع → علت/تأثیر → بسته شدن احساسی.  
عکس شخصیت اصلی اختیاری است؛ برای Pro بهتر است.

کیفیت: **Light** (پیش‌نویس FFmpeg) یا **Pro** (Remotion محلی + Williams timing).  
خروجی: `out/<job>/render.mp4`.

```powershell
python __main__.py render --brief "Beat1.`n`nThen beat2 because X.`n`nClose." --quality light
python __main__.py render --brief "..." --quality pro --character path\to\hero.png
streamlit run app.py
```
