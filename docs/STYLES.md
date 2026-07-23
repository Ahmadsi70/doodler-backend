# Styles (Story)

کاتالوگ فقط استایل‌های `studio_story` را نگه می‌دارد.

- پیش‌فرض: `symmetrical_pastel_cinema`
- منبع: `libraries/styles/starter_pack.json` + `studio_style_map.json`

```powershell
python -c "from tools.style_catalog import styles_for_studio; print([s['style_id'] for s in styles_for_studio('studio_story')])"
```

Pro Remotion از `engine.grade` / `pace` / `camera` برای palette و حرکت استفاده می‌کند.
