# Story Pack — اشتراک‌گذاری انیمیشن قابل‌تعویض

هدف: کد/دستور پخت انیمیشن را ذخیره کنی و به کسی بدهی؛ او فقط عکس کاراکتر را عوض کند و ویدیو بسازد.

## محتویات پک

```text
my_film/
  pack.json
  studio_spec.json      ← زمان‌بندی، دوربین، pose، متن شات‌ها
  README.md
  assets/
    character.png       ← گیرنده این فایل را عوض می‌کند
```

مسیرها **نسبی**اند (`assets/character.png`) تا روی سیستم دیگری هم کار کند.

## نویسنده (تو)

```powershell
python __main__.py pack-export --spec examples\studio_spec.json --out packs\my_film --character C:\path\hero.png
# پوشه packs\my_film را zip کن و بفرست
```

از روی job تمام‌شده:

```powershell
python __main__.py pack-export --spec ignored --from-job out\<job_id> --out packs\from_job
```

## گیرنده

```powershell
# 1) عکس خودش را جایگذاری کند
python __main__.py pack-swap --pack packs\my_film --character C:\their\photo.png

# 2) صدور بستهٔ ساخت (نمایشنامه + پرامپت + کد موتور)
python __main__.py pack-export --pack packs\my_film --quality pro
# alias قدیمی: pack-render همان export است — Story MP4 نمی‌سازد
```

یا مستقیم:

```powershell
python __main__.py export --pack packs\my_film --character C:\their\photo.png --quality light
```

گیرنده برای عوض کردن داستان می‌تواند `studio_spec.json` را هم ویرایش کند (متن شات، pose، دوربین).
