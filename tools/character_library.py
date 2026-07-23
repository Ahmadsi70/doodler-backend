"""
Character library — persistent profiles shared across films.

Why: users keep one hero identity (portrait + layers + appearance text) so every
job/export/Remotion pack resolves the same assets without re-uploading.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{1,63}$")


def default_library_root() -> Path:
    """Library root under .story/characters (override in tests via monkeypatch)."""
    return _ROOT / ".story" / "characters"


def _slug_id(name_fa: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", name_fa.strip())[:40].strip("_").lower()
    if not base or not base[0].isalpha():
        base = f"char_{base or 'x'}"
    return base[:64]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_image(src: Path | str, dest: Path) -> Path:
    src_p = Path(src)
    if not src_p.is_file():
        raise FileNotFoundError(src_p)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_p, dest)
    return dest.resolve()


def create_character(
    *,
    name_fa: str,
    appearance_fa: str = "",
    portrait_path: Path | str,
    layers: dict[str, str | None] | None = None,
    character_id: str | None = None,
    library_root: Path | None = None,
) -> dict[str, Any]:
    """
    Create a character profile folder and return the public profile dict.

    Idempotent replace if the same id already exists (overwrites assets).
    """
    root = Path(library_root) if library_root else default_library_root()
    cid = (character_id or _slug_id(name_fa)).strip()
    if not _ID_RE.match(cid):
        raise ValueError(f"invalid character_id: {cid!r}")
    folder = root / cid
    folder.mkdir(parents=True, exist_ok=True)
    portrait_dest = _copy_image(portrait_path, folder / "portrait.png")
    layer_out: dict[str, str | None] = {"body": None, "head": None, "hand": None}
    layers_dir = folder / "layers"
    for key in ("body", "head", "hand"):
        src = (layers or {}).get(key)
        if src:
            rel = f"layers/{key}.png"
            _copy_image(src, folder / rel)
            layer_out[key] = rel
        else:
            layer_out[key] = None
    profile = {
        "schema": "character_profile#v1",
        "id": cid,
        "name_fa": (name_fa or cid).strip(),
        "appearance_fa": (appearance_fa or "").strip(),
        "portrait": "portrait.png",
        "layers": layer_out,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(folder / "profile.json", profile)
    _ = portrait_dest
    if any(layer_out.values()):
        layers_dir.mkdir(parents=True, exist_ok=True)
    return profile


def list_characters(*, library_root: Path | None = None) -> list[dict[str, Any]]:
    """List character profiles (id, name_fa, appearance_fa)."""
    root = Path(library_root) if library_root else default_library_root()
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        prof = get_character(child.name, library_root=root)
        if prof:
            out.append(
                {
                    "id": prof["id"],
                    "name_fa": prof.get("name_fa") or prof["id"],
                    "appearance_fa": prof.get("appearance_fa") or "",
                }
            )
    return out


def get_character(
    character_id: str,
    *,
    library_root: Path | None = None,
) -> dict[str, Any] | None:
    """Load profile.json for an id, or None."""
    root = Path(library_root) if library_root else default_library_root()
    path = root / character_id / "profile.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    data["id"] = character_id
    return data


def resolve_character(
    character_id: str,
    *,
    library_root: Path | None = None,
) -> dict[str, Any]:
    """
    Resolve absolute paths for portrait + layers + appearance text.

    Raises FileNotFoundError if profile or portrait missing.
    """
    root = Path(library_root) if library_root else default_library_root()
    profile = get_character(character_id, library_root=root)
    if not profile:
        raise FileNotFoundError(f"character not found: {character_id}")
    folder = root / character_id
    portrait = folder / str(profile.get("portrait") or "portrait.png")
    if not portrait.is_file():
        raise FileNotFoundError(portrait)
    layers_abs: dict[str, str | None] = {"body": None, "head": None, "hand": None}
    for key in ("body", "head", "hand"):
        rel = (profile.get("layers") or {}).get(key)
        if rel:
            p = folder / str(rel)
            layers_abs[key] = str(p.resolve()) if p.is_file() else None
    return {
        "id": character_id,
        "name_fa": profile.get("name_fa") or character_id,
        "appearance_fa": profile.get("appearance_fa") or "",
        "character_path": str(portrait.resolve()),
        "layers": layers_abs,
        "profile": profile,
    }


def materialize_character_into_job(
    character_id: str,
    job_dir: Path | str,
    *,
    library_root: Path | None = None,
) -> dict[str, Any]:
    """
    Copy character assets into ``job_dir/assets/character/`` for portable export.

    Returns paths under the job directory.
    """
    resolved = resolve_character(character_id, library_root=library_root)
    dest_root = Path(job_dir) / "assets" / "character"
    dest_root.mkdir(parents=True, exist_ok=True)
    portrait = _copy_image(resolved["character_path"], dest_root / "portrait.png")
    layers_out: dict[str, str | None] = {"body": None, "head": None, "hand": None}
    for key, src in (resolved.get("layers") or {}).items():
        if src and Path(src).is_file():
            layers_out[key] = str(_copy_image(src, dest_root / f"{key}.png"))
    meta = {
        "character_id": character_id,
        "name_fa": resolved.get("name_fa"),
        "appearance_fa": resolved.get("appearance_fa"),
        "character_path": str(portrait),
        "layers": layers_out,
    }
    _write_json(dest_root / "profile.json", meta)
    return meta
