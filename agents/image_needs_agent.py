"""
ImageNeedsAgent — decide which still assets a shot needs for external image tools.

Why: one shot ≠ one vague prompt; assembly needs typed assets (keyframe, ref,
establishing, insert) grounded in screenplay + framing from craft.
"""

from __future__ import annotations

from typing import Any

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore

_ASPECT = "16:9"

_CROP_FA = {
    "WS": "قاب عریض؛ شخصیت کوچک در محیط؛ لبهٔ امن ۱۰٪ از چهار طرف",
    "MS": "نیمه‌تنه؛ سر تا کمر؛ فضای نگاه مطابق composition",
    "CU": "کلوزآپ موضوع؛ برش تنگ؛ پس‌زمینه محو/ساده",
    "insert": "اینسرت شیء؛ کل فریم روی prop؛ بدون چهرهٔ کامل",
}


def _anchor_for_shot(
    sh: ShotControl,
    index: int,
    *,
    screenplay: dict[str, Any] | None,
) -> str:
    scenes = list((screenplay or {}).get("scenes") or [])
    if index < len(scenes):
        action = str(scenes[index].get("action") or "").strip()
        if action:
            return action
    md = str((screenplay or {}).get("screenplay_md") or "")
    if md and sh.action:
        return sh.action.strip()
    return (sh.action or sh.title or f"shot {index}").strip()


def _story_row(storyboard: dict[str, Any] | None, index: int) -> dict[str, Any]:
    for row in (storyboard or {}).get("shots") or []:
        if int(row.get("shot_id", -1)) == index:
            return dict(row)
    shots = list((storyboard or {}).get("shots") or [])
    if index < len(shots):
        return dict(shots[index])
    return {}


def _framing(sh: ShotControl, *, kind: str) -> dict[str, str]:
    size = "insert" if kind == "insert" else str(sh.shot_size or "MS")
    return {
        "shot_size": size if kind == "insert" else str(sh.shot_size or "MS"),
        "composition": str(sh.composition or "C"),
        "aspect": _ASPECT,
        "crop_note_fa": _CROP_FA.get(size, _CROP_FA["MS"]),
    }


def _wants_insert(sh: ShotControl) -> bool:
    if str(sh.shot_size or "").upper() == "CU":
        return True
    action = (sh.action or "").lower()
    cues = ("قلم", "جعبه", "نامه", "فانوس", "دست", "در ", "کلید", "کتاب")
    return any(c in action for c in cues) and str(sh.shot_size or "").upper() in {
        "CU",
        "MS",
    }


def run_image_needs_agent(
    spec: StudioSpec,
    *,
    screenplay: dict[str, Any] | None = None,
    storyboard: dict[str, Any] | None = None,
    breakdown: dict[str, Any] | None = None,
    character_appearance_fa: str | None = None,
) -> dict[str, Any]:
    """
    Build typed image asset list for the film.

    Always: one character_ref + one keyframe per shot.
    Extra: establishing on entrance/WS; insert on CU/object beats.
    """
    _ = breakdown  # optional future grounding
    appearance = (character_appearance_fa or "").strip()
    if not appearance:
        try:
            appearance = spec.resolved_appearance_fa()
        except Exception:  # noqa: BLE001
            appearance = ""
    anchor_ref = appearance or (spec.title or "قهرمان").strip()
    assets: list[dict[str, Any]] = []
    assets.append(
        {
            "asset_id": "character_ref",
            "shot_id": None,
            "kind": "character_ref",
            "role_fa": "مرجع ثبات شخصیت برای همه شات‌ها",
            "screenplay_anchor": anchor_ref,
            "appearance_fa": appearance,
            "framing": {
                "shot_size": "MS",
                "composition": "C",
                "aspect": _ASPECT,
                "crop_note_fa": "تمام‌قد یا نیمه‌تنه؛ پس‌زمینه خنثی؛ هویت ثابت",
            },
            "timeline_slot": "global/character_ref",
            "verb": "",
            "focal_point": "character",
        }
    )
    for i, sh in enumerate(spec.shots):
        anchor = _anchor_for_shot(sh, i, screenplay=screenplay)
        sb = _story_row(storyboard, i)
        verb = str(sb.get("verb") or "")
        focal = str(sb.get("focal_point") or "")
        if str(sh.story_beat) == "entrance" or str(sh.shot_size or "").upper() == "WS":
            assets.append(
                {
                    "asset_id": f"shot_{i:02d}_establishing",
                    "shot_id": i,
                    "kind": "establishing",
                    "role_fa": "پلان معرف مکان",
                    "screenplay_anchor": anchor,
                    "framing": _framing(sh, kind="establishing"),
                    "timeline_slot": f"shot_{i:02d}/establishing",
                    "verb": verb,
                    "focal_point": focal or "environment",
                }
            )
        assets.append(
            {
                "asset_id": f"shot_{i:02d}_key",
                "shot_id": i,
                "kind": "keyframe",
                "role_fa": "فریم کلید اکشن شات",
                "screenplay_anchor": anchor,
                "framing": _framing(sh, kind="keyframe"),
                "timeline_slot": f"shot_{i:02d}/still",
                "verb": verb,
                "focal_point": focal,
            }
        )
        if _wants_insert(sh):
            assets.append(
                {
                    "asset_id": f"shot_{i:02d}_insert",
                    "shot_id": i,
                    "kind": "insert",
                    "role_fa": "اینسرت جزئیات شیء/دست",
                    "screenplay_anchor": anchor,
                    "framing": _framing(sh, kind="insert"),
                    "timeline_slot": f"shot_{i:02d}/insert",
                    "verb": verb,
                    "focal_point": focal or "prop",
                }
            )
    return {
        "agent": "ImageNeedsAgent",
        "version": "1",
        "schema": "image_needs_agent.md#v1",
        "title": spec.title,
        "asset_count": len(assets),
        "assets": assets,
        "assembly_notes_fa": (
            "هر asset را جدا بسازید؛ character_ref را در همه شات‌ها ثابت نگه دارید. "
            "aspect همه ۱۶:۹؛ crop_note را در ابزار رعایت کنید. "
            "timeline_slot مسیر جایگذاری در تایم‌لاین ویدیو است."
        ),
    }
