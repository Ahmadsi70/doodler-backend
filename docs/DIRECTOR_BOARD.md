# Director Board — کنترل کاربر قبل از صدور

جریان:

```text
Brief / کار در اپ
  → طراحی کامل (ایجنت‌ها → StudioSpec)
  → پیش‌نمایش بسته + دانلود اختیاری     ← توقف
  → اصلاح دستی یا پرامپت پچ
  → Approve
  → screenplay + prompts + کد موتور
  → (اختیاری) رندر مستقیم MP4 یا کد آماده اجرا (فاز E)
```

## UI

```powershell
streamlit run app.py
```

مراحل: Brief → Design Preview → Approve & Export

ظاهر: پالت لاکچری **Ink Forest × Antique Brass** روی زمینهٔ pearl، فونت Spectral + Figtree، ریل مراحل سه‌ستونه، پنل‌های بخش‌بندی‌شده. تم در `.streamlit/config.toml`.

مرحلهٔ پیش‌نمایش: تب‌های **نمایشنامه / توضیح / پرامپت‌ها / کد** قبل از Approve.

## CLI

```powershell
python __main__.py design --brief "Enter.`n`nThen shock because fire.`n`nExit." --out out\design1
python __main__.py revise --job out\design1 --prompt "shot 2 camera static pose idle"
python __main__.py export --job out\design1
```

فقط Approve بدون صدور:

```powershell
python __main__.py approve-render --job out\design1 --approve-only
```

(`approve-render` و `render` aliasهای قدیمی هستند — خروجی همان **export** است.)

## کنترل بیشتر

- قفل فیلد شات (camera/pose/…) تا revise پرامپت عوضشان نکند
- ویرایش دستی هر شات در UI
- انتخاب موتور صدور: prompts / remotion / slideshow
- دانلود `studio_spec.json` + `design_preview.md`
- بدون Approve صدور قفل است
