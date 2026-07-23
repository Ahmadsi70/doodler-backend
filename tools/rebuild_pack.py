"""
Personal rebuild pack — drop README + rebuild script into each job workspace.

Why: user mastery over outputs without depending on the Streamlit UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

README_NAME = "README_REBUILD.md"
SCRIPT_NAME = "rebuild_video.py"
MANIFEST_NAME = "rebuild_manifest.json"

_REBUILD_SCRIPT = r'''"""Re-encode Light slideshow PNGs → render_rebuilt.mp4 (FFmpeg)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLIDES = ROOT / "slides"
OUT = ROOT / "render_rebuilt.mp4"
MANIFEST = ROOT / "rebuild_manifest.json"


def find_ffmpeg() -> str:
    env = (os.environ.get("FFMPEG_PATH") or "").strip()
    if env and Path(env).is_file():
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    raise SystemExit("ffmpeg not found — set FFMPEG_PATH or install FFmpeg")


def main() -> int:
    fps = 24
    sec = 2.5
    if MANIFEST.is_file():
        meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
        fps = int(meta.get("fps") or fps)
        sec = float(meta.get("seconds_per_slide") or sec)
    pngs = sorted(SLIDES.glob("slide_*.png"))
    if not pngs:
        print("No slides/slide_*.png — cannot rebuild Light path", file=sys.stderr)
        return 2
    ff = find_ffmpeg()
    list_file = ROOT / "_slides_concat.txt"
    lines: list[str] = []
    for p in pngs:
        lines.append(f"file '{p.resolve().as_posix()}'")
        lines.append(f"duration {sec}")
    lines.append(f"file '{pngs[-1].resolve().as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        ff,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-vsync",
        "vfr",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        str(OUT),
    ]
    print(" ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    list_file.unlink(missing_ok=True)
    if r.returncode != 0:
        return r.returncode
    print("OK", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_rebuild_pack(
    job_dir: Path | str,
    *,
    brief: str = "",
    artifacts: dict[str, Any] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Write rebuild helpers next to ``render.mp4``. Returns written paths."""
    root = Path(job_dir)
    root.mkdir(parents=True, exist_ok=True)
    artifacts = dict(artifacts or {})
    extras = dict(extras or {})
    mp4 = artifacts.get("render_mp4") or str(root / "render.mp4")
    slides = root / "slides"
    has_slides = slides.is_dir() and any(slides.glob("slide_*.png"))

    readme = f"""# Rebuild this Story job

Job folder: `{root.resolve()}`

## Artifacts

- `render.mp4` — final video
- `story_props.json` — Remotion composition props
- `style_profile.json` / `render_profile.json`
- `story_supervisor.json`
- `agents/` — Storyboard → Continuity
- `slides/` — Light draft PNGs (if Light path)

## Rebuild from slides (Light)

```powershell
python rebuild_video.py
```

## Re-run

From `C:\\Users\\badri\\Story`:

```powershell
python __main__.py render --brief "$(Get-Content -Raw brief.txt)" --quality light
python __main__.py render --brief "$(Get-Content -Raw brief.txt)" --quality pro
```

## Notes

- Pro = Remotion local (not Lambda).
- Keep `slides/` / `story_props.json` next to rebuild helpers.
"""
    readme_path = root / README_NAME
    readme_path.write_text(readme, encoding="utf-8")

    script_path = root / SCRIPT_NAME
    script_path.write_text(_REBUILD_SCRIPT, encoding="utf-8")

    fps = 24
    sec_slide = 2.5
    prof_path = root / "render_profile.json"
    if prof_path.is_file():
        try:
            prof = json.loads(prof_path.read_text(encoding="utf-8"))
            fps = int(prof.get("fps") or fps)
            sec_slide = float(prof.get("seconds_per_slide") or sec_slide)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    manifest = {
        "brief": brief,
        "render_mp4": mp4,
        "has_slides": has_slides,
        "fps": fps,
        "seconds_per_slide": sec_slide,
        "quality": extras.get("quality"),
        "style_id": extras.get("style_id"),
        "character_path": extras.get("character_path") or extras.get("character_main"),
    }
    man_path = root / MANIFEST_NAME
    man_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if brief.strip():
        (root / "brief.txt").write_text(brief.strip() + "\n", encoding="utf-8")

    return {
        "readme": str(readme_path.resolve()),
        "script": str(script_path.resolve()),
        "manifest": str(man_path.resolve()),
    }
