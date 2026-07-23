# کاراکتر سراسری (Character Library)

کاربر یک پروفایل می‌سازد و در همه فیلم‌ها همان هویت را انتخاب می‌کند.

## مسیر

```text
.story/characters/<id>/
  profile.json
  portrait.png
  layers/body.png | head.png | hand.png   # اختیاری
```

## API

```python
from tools.character_library import create_character, list_characters, resolve_character

create_character(
    name_fa="لیلا",
    appearance_fa="موی تیره، لباس آبی",
    portrait_path=r"C:\path\hero.png",
    character_id="leila_v1",  # اختیاری
)
resolve_character("leila_v1")  # → character_path + layers + appearance_fa
```

## StudioSpec

فیلد اختیاری `character_id` — اگر `character_path` خالی باشد از library resolve می‌شود.

## UI

Director Board → تنظیمات پیشرفته → **کاراکتر ذخیره‌شده**  
یا آپلود + نام پروفایل برای ساخت جدید.
