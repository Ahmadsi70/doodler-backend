"""
Portable Story Pack — share Spec + assets so others swap characters and re-render.

Why: user-owned control requires a folder you can zip/send: studio_spec.json with
relative ``assets/`` paths, not machine-absolute paths.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

try:
    from studio_spec import StudioAssets, StudioSpec
except ImportError:
    from ..studio_spec import StudioAssets, StudioSpec  # type: ignore

CHARACTER_REL = "assets/character.png"
PACK_MANIFEST = "pack.json"
SPEC_NAME = "studio_spec.json"
README_NAME = "README.md"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _resolve_against(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    p = Path(value)
    if p.is_file():
        return str(p.resolve())
    cand = (root / value).resolve()
    if cand.is_file():
        return str(cand)
    return None


def export_story_pack(
    spec: StudioSpec,
    dest_dir: Path | str,
    *,
    pack_id: str = "story_pack",
    copy_character: bool = True,
) -> Path:
    """
    Export a portable pack directory.

    Copies character to ``assets/character.png`` when present and rewrites Spec
    to pack-relative paths.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    assets = dest / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    data = spec.to_public_dict()
    src_char = spec.resolved_character()
    has_char = bool(src_char and Path(str(src_char)).is_file() and copy_character)

    if has_char:
        shutil.copy2(str(src_char), dest / CHARACTER_REL)
    else:
        (assets / "PUT_CHARACTER_HERE.txt").write_text(
            "Place your photo as character.png in this folder, then export.\n",
            encoding="utf-8",
        )

    rel = CHARACTER_REL.replace("\\", "/")
    data["character_path"] = rel
    assets_block = dict(data.get("assets") or {})
    assets_block["character_path"] = rel

    slides_out: list[str] = []
    for i, slide in enumerate((spec.assets.slide_images if spec.assets else []) or []):
        p = Path(slide)
        if p.is_file():
            name = f"slide_{i:02d}{p.suffix.lower() or '.png'}"
            shutil.copy2(p, assets / name)
            slides_out.append(f"assets/{name}")
    assets_block["slide_images"] = slides_out
    data["assets"] = assets_block

    _write_json(dest / SPEC_NAME, data)
    _write_json(
        dest / PACK_MANIFEST,
        {
            "pack_id": pack_id,
            "schema_version": "1.0.0",
            "title": spec.title,
            "spec": SPEC_NAME,
            "character_slot": rel,
            "has_character": has_char,
            "how_to": [
                "Replace assets/character.png with your photo",
                "python __main__.py export --spec studio_spec.json --out out/job",
            ],
        },
    )
    (dest / README_NAME).write_text(
        _readme_text(spec.title, pack_id), encoding="utf-8"
    )
    return dest.resolve()


def _readme_text(title: str, pack_id: str) -> str:
    return f"""# Story Pack: {title}

Pack id: `{pack_id}`

Portable animation recipe. Timing / camera / poses live in `studio_spec.json`.
Recipients mainly swap media.

## For the person who receives this pack

1. Put your character photo at `assets/character.png`
2. Optional: edit shot `action` text in `studio_spec.json`
3. From the Story project:

```powershell
python __main__.py export --spec studio_spec.json --out out\\from_pack
```

## For the author (create a pack)

```powershell
python __main__.py pack-export --spec examples\\studio_spec.json --out packs\\my_film --character C:\\path\\hero.png
```

Zip the pack folder and send it. Do not rely on absolute paths from your PC.
"""


def load_pack_spec(pack_dir: Path | str) -> StudioSpec:
    """Load Spec and resolve relative asset paths against the pack root."""
    root = Path(pack_dir).resolve()
    spec_path = root / SPEC_NAME
    if not spec_path.is_file():
        raise FileNotFoundError(f"Missing {SPEC_NAME} in {root}")
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    spec = StudioSpec.model_validate(data)

    char_abs = _resolve_against(root, spec.resolved_character())
    slides: list[str] = []
    for s in spec.assets.slide_images or []:
        resolved = _resolve_against(root, s)
        if resolved:
            slides.append(resolved)

    assets = StudioAssets(
        character_path=char_abs,
        slide_images=slides,
    )
    return spec.model_copy(
        update={
            "character_path": char_abs,
            "assets": assets,
        }
    )


def swap_pack_character(pack_dir: Path | str, new_image: Path | str) -> Path:
    """Replace ``assets/character.png`` in an existing pack."""
    root = Path(pack_dir).resolve()
    src = Path(new_image)
    if not src.is_file():
        raise FileNotFoundError(f"Character image not found: {src}")
    dest = root / CHARACTER_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    spec_path = root / SPEC_NAME
    if spec_path.is_file():
        data = json.loads(spec_path.read_text(encoding="utf-8"))
        rel = CHARACTER_REL.replace("\\", "/")
        data["character_path"] = rel
        assets = dict(data.get("assets") or {})
        assets["character_path"] = rel
        data["assets"] = assets
        _write_json(spec_path, data)
    note = root / "assets" / "PUT_CHARACTER_HERE.txt"
    if note.is_file():
        note.unlink()
    return dest


def export_pack_from_job(job_dir: Path | str, dest_dir: Path | str) -> Path:
    """Export pack from a finished job that contains studio_spec.json."""
    job = Path(job_dir)
    spec_file = job / SPEC_NAME
    if not spec_file.is_file():
        raise FileNotFoundError(f"Job has no {SPEC_NAME}: {job}")
    from tools.studio_api import load_studio_spec

    spec = load_studio_spec(spec_file)
    char = spec.resolved_character()
    if not char or not Path(str(char)).is_file():
        uploads = job / "uploads"
        if uploads.is_dir():
            for cand in sorted(uploads.glob("character_*")):
                if cand.is_file():
                    spec = spec.model_copy(update={"character_path": str(cand)})
                    break
        for folder in (job, job / "public"):
            p = folder / "character.png"
            if p.is_file():
                spec = spec.model_copy(update={"character_path": str(p)})
                break
    return export_story_pack(spec, dest_dir, pack_id=job.name)
