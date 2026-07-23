"""Path B — Story asset contract: character_main + optional props."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from tools.studio_profiles import STORY_STUDIO
except ImportError:
    from .studio_profiles import STORY_STUDIO

MANIFEST_NAME = "assets_manifest.json"

ROLE_META = {
    "character_main": {
        "label_fa": "شخصیت اصلی",
        "label_en": "Main character",
        "hint_fa": "پیشنهادی برای Pro cutout",
    },
    "character_secondary": {
        "label_fa": "شخصیت فرعی",
        "label_en": "Secondary",
        "hint_fa": "اختیاری",
    },
    "prop": {
        "label_fa": "پراپ",
        "label_en": "Prop",
        "hint_fa": "اختیاری",
    },
}


def _role(role: str, *, recommended: bool = False, max_count: int = 1) -> dict[str, Any]:
    meta = ROLE_META.get(role, {})
    return {
        "role": role,
        "required": False,
        "recommended": recommended,
        "max": max_count,
        "label_fa": meta.get("label_fa", role),
        "label_en": meta.get("label_en", role),
        "hint_fa": meta.get("hint_fa", ""),
    }


STUDIO_CONTRACTS = {
    STORY_STUDIO: {
        "studio": STORY_STUDIO,
        "min_photos": 0,
        "ideal_photos": 1,
        "summary_fa": "حداقل ۱ عکس شخصیت اصلی ایده‌آل است؛ بدون آن Remotion با silhouette کار می‌کند.",
        "summary_en": "Ideal: main character photo for cutout 2D.",
        "roles": [
            _role("character_main", recommended=True, max_count=1),
            _role("character_secondary", recommended=False, max_count=4),
            _role("prop", recommended=False, max_count=6),
        ],
    },
}


@dataclass
class AssetEvalResult:
    studio: str
    ok: bool
    min_photos: int
    ideal_photos: int
    provided_photos: int
    missing_required: list[str] = field(default_factory=list)
    recommended_missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checklist: list[dict[str, Any]] = field(default_factory=list)
    summary_fa: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "studio": self.studio,
            "ok": self.ok,
            "min_photos": self.min_photos,
            "ideal_photos": self.ideal_photos,
            "provided_photos": self.provided_photos,
            "missing_required": list(self.missing_required),
            "recommended_missing": list(self.recommended_missing),
            "warnings": list(self.warnings),
            "checklist": list(self.checklist),
            "summary_fa": self.summary_fa,
        }


def get_studio_contract(studio: str | None = None) -> dict[str, Any]:
    return dict(STUDIO_CONTRACTS[STORY_STUDIO])


def _as_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    s = str(value).strip()
    return [s] if s else []


def count_provided_photos(provided: dict[str, Any] | None) -> int:
    provided = provided or {}
    n = 0
    for key in ("character_main", "character_path", "character_secondary", "prop", "slide_images"):
        n += len(_as_path_list(provided.get(key)))
    return n


def _paths_for_role(role: str, provided: dict[str, Any]) -> list[str]:
    aliases = {
        "character_main": ("character_main", "character_path"),
        "character_secondary": ("character_secondary",),
        "prop": ("prop", "props"),
    }
    out: list[str] = []
    for key in aliases.get(role, (role,)):
        out.extend(_as_path_list(provided.get(key)))
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def evaluate_assets(studio: str, provided: dict[str, Any] | None = None) -> AssetEvalResult:
    contract = get_studio_contract(studio)
    provided = dict(provided or {})
    provided_n = count_provided_photos(provided)
    missing_rec: list[str] = []
    checklist: list[dict[str, Any]] = []
    warnings: list[str] = []
    for role_spec in contract["roles"]:
        role = str(role_spec["role"])
        paths = _paths_for_role(role, provided)
        filled = len(paths) > 0
        checklist.append(
            {
                "role": role,
                "label_fa": role_spec.get("label_fa", role),
                "filled": filled,
                "count": len(paths),
            }
        )
        if role_spec.get("recommended") and not filled:
            missing_rec.append(role)
            if role == "character_main":
                warnings.append("No character photo — Remotion uses silhouette placeholder.")
    return AssetEvalResult(
        studio=str(contract["studio"]),
        ok=True,
        min_photos=int(contract["min_photos"]),
        ideal_photos=int(contract["ideal_photos"]),
        provided_photos=provided_n,
        recommended_missing=missing_rec,
        warnings=warnings,
        checklist=checklist,
        summary_fa=str(contract.get("summary_fa") or ""),
    )


def build_assets_manifest(
    studio: str,
    provided: dict[str, Any] | None = None,
    *,
    job_id: str | None = None,
    sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    contract = get_studio_contract(studio)
    provided = dict(provided or {})
    sources = dict(sources or {})
    ev = evaluate_assets(studio, provided)
    roles_out: dict[str, Any] = {}
    for role_spec in contract["roles"]:
        role = str(role_spec["role"])
        paths = _paths_for_role(role, provided)
        if role_spec.get("max", 1) == 1:
            roles_out[role] = {
                "path": paths[0] if paths else None,
                "count": len(paths),
                "source": sources.get(role),
            }
        else:
            roles_out[role] = {
                "paths": paths,
                "count": len(paths),
                "source": sources.get(role),
            }
    return {
        "studio": STORY_STUDIO,
        "job_id": job_id,
        "evaluation": ev.to_dict(),
        "roles": roles_out,
    }


def write_assets_manifest(job_dir: Path | str, manifest: dict[str, Any]) -> Path:
    path = Path(job_dir) / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
