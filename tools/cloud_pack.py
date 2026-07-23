"""
Cloud render pack — ZIP Remotion scaffold + export props for remote servers.

Why: users need one downloadable archive to upload to a VPS/GPU box and run
``npx remotion render`` without cloning the whole Story repo.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parents[1]
_REMOTION = _ROOT / "remotion"

# Minimal files for a runnable Remotion project (no node_modules).
_REMOTION_FILES = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "remotion.config.ts",
    "src/index.ts",
    "src/Root.tsx",
    "src/StoryNarrative.tsx",
    "src/CharacterRig.tsx",
    "src/CharacterLayers.tsx",
)


def _add_tree(zf: zipfile.ZipFile, src: Path, arc_prefix: str) -> None:
    if not src.is_dir():
        return
    for path in src.rglob("*"):
        if path.is_file():
            zf.write(path, f"{arc_prefix}/{path.relative_to(src).as_posix()}")


def _copy_remotion_scaffold(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for rel in _REMOTION_FILES:
        src = _REMOTION / rel
        if not src.is_file():
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    # Optional audio cues for timeline playback
    pub_audio = _REMOTION / "public" / "audio"
    if pub_audio.is_dir():
        out_audio = dest / "public" / "audio"
        out_audio.mkdir(parents=True, exist_ok=True)
        for wav in list(pub_audio.glob("*.wav"))[:40]:
            shutil.copy2(wav, out_audio / wav.name)


def prepare_cloud_render_dir(export_root: Path | str, dest_dir: Path | str) -> Path:
    """
    Build a folder: remotion/ (scaffold) + props + character + CLOUD_RENDER.md.

    ``export_root`` is a Story export/ directory containing engines/remotion/.
    """
    export_root = Path(export_root)
    dest = Path(dest_dir)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    remotion_out = dest / "remotion"
    _copy_remotion_scaffold(remotion_out)

    eng = export_root / "engines" / "remotion"
    props_src = eng / "story_props.json"
    if props_src.is_file():
        public = remotion_out / "public"
        public.mkdir(parents=True, exist_ok=True)
        shutil.copy2(props_src, public / "story_props.json")
        shutil.copy2(props_src, remotion_out / "story_props.json")

    char_candidates: Iterable[Path] = (
        eng / "assets" / "character.png",
        export_root / "assets" / "character" / "portrait.png",
    )
    assets = remotion_out / "public"
    assets.mkdir(parents=True, exist_ok=True)
    for cand in char_candidates:
        if cand.is_file():
            shutil.copy2(cand, assets / "character.png")
            break

    # Keep prompts/screenplay for human operators on the server
    for name in ("screenplay.md", "explanation.md", "studio_spec.json"):
        src = export_root / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    prompts = export_root / "prompts"
    if prompts.is_dir():
        _add_tree_to_dir(prompts, dest / "prompts")

    cloud_md = eng / "CLOUD_RENDER.md"
    if cloud_md.is_file():
        shutil.copy2(cloud_md, dest / "CLOUD_RENDER.md")
    else:
        (dest / "CLOUD_RENDER.md").write_text(
            _default_cloud_render_md(), encoding="utf-8"
        )
    return dest.resolve()


def _add_tree_to_dir(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if path.is_file():
            out = dest / path.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)


def build_cloud_render_zip(
    export_root: Path | str,
    zip_path: Path | str,
    *,
    work_dir: Path | str | None = None,
) -> Path:
    """Zip a cloud-ready Remotion pack; returns path to the .zip file."""
    export_root = Path(export_root)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(work_dir) if work_dir else zip_path.parent / f"{zip_path.stem}_staging"
    prepare_cloud_render_dir(export_root, staging)
    if zip_path.is_file():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(staging).as_posix())
    shutil.rmtree(staging, ignore_errors=True)
    return zip_path.resolve()


def _default_cloud_render_md() -> str:
    return (
        "# Cloud render (Remotion)\n\n"
        "1. Unzip on the server (8 CPU / 16GB RAM recommended).\n"
        "2. `cd remotion && npm install`\n"
        "3. Render:\n\n"
        "```bash\n"
        "npx remotion render src/index.ts StoryNarrative out/film.mp4 "
        "--props=./story_props.json\n"
        "```\n\n"
        "See https://www.remotion.dev/docs/cli/render\n"
    )
