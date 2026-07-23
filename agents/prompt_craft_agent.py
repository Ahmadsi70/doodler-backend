"""
PromptCraftAgent — per-shot / per-asset prompts for external image tools.

Why: users paste prompts elsewhere; Story prepares still instructions grounded
in screenplay anchors, storyboard focal, and ImageNeeds framing (not vague templates).
"""

from __future__ import annotations

from typing import Any

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore

_DEFAULT_NEGATIVE = (
    "متن روی تصویر، واترمارک، لوگو، دست اضافی، چهرهٔ distorted، "
    "blur، low quality، collage، split panel، قاب اشتباه، برش سر"
)


def _story_row(storyboard: dict[str, Any] | None, index: int) -> dict[str, Any]:
    for row in (storyboard or {}).get("shots") or []:
        if int(row.get("shot_id", -1)) == index:
            return dict(row)
    shots = list((storyboard or {}).get("shots") or [])
    if index < len(shots):
        return dict(shots[index])
    return {}


def _prompt_asset(
    *,
    asset: dict[str, Any],
    sh: ShotControl | None,
    spec: StudioSpec,
    cine_row: dict[str, Any] | None,
    appearance_fa: str = "",
) -> dict[str, Any]:
    cine = cine_row or {}
    framing = dict(asset.get("framing") or {})
    aspect = framing.get("aspect") or "16:9"
    crop = framing.get("crop_note_fa") or ""
    size = framing.get("shot_size") or (sh.shot_size if sh else "MS")
    composition = framing.get("composition") or (sh.composition if sh else "C")
    lighting = (cine.get("lighting") if cine else None) or (sh.lighting if sh else "three_point")
    kind = str(asset.get("kind") or "keyframe")
    anchor = str(asset.get("screenplay_anchor") or (sh.action if sh else "")).strip()
    verb = str(asset.get("verb") or "")
    focal = str(asset.get("focal_point") or "")
    look = (
        appearance_fa
        or str(asset.get("appearance_fa") or "")
        or ""
    ).strip()
    lines = [
        f"Asset `{asset.get('asset_id')}` · kind={kind} · فیلم «{spec.title}»",
        f"لنگر فیلم‌نامه: {anchor}",
        f"نسبت تصویر: {aspect} · اندازه: {size} · ترکیب: {composition}",
        f"کات/کراپ: {crop}",
    ]
    if look:
        lines.append(f"هویت کاراکتر (قفل): {look}")
    if focal:
        lines.append(f"focal_point: {focal}")
    if verb:
        lines.append(f"verb/storyboard: {verb}")
    if sh is not None:
        lines.append(
            f"دوربین: {cine.get('camera') or sh.camera} · لنز: {cine.get('lens') or sh.lens} · نور: {lighting}"
        )
        lines.append(
            f"pose: {sh.pose} · expression: {sh.expression} · beat: {sh.story_beat}"
        )
        if sh.dialogue and kind == "keyframe":
            lines.append(f"دیالوگ (نه روی تصویر): {sh.dialogue}")
    lines.append(f"سبک: {spec.style_id} · grade: {spec.grade} · emotion: {spec.emotion}")
    if kind == "character_ref":
        lines.append("خروجی: مرجع شخصیت ثابت — همان چهره/لباس در همه شات‌ها.")
    elif kind == "establishing":
        lines.append("خروجی: پلان معرف مکان؛ فضای محیط غالب.")
    elif kind == "insert":
        lines.append("خروجی: اینسرت جزئیات؛ شیء پر فریم.")
    else:
        lines.append("خروجی: فریم کلید سینمایی 2D هم‌تراز اکشن شات؛ همان هویت character_ref.")
    lines.append(f"timeline_slot: {asset.get('timeline_slot')}")
    negative = _DEFAULT_NEGATIVE
    if kind == "insert":
        negative += "، پرترهٔ تمام‌چهره، شلوغی پس‌زمینه"
    if sh is not None and sh.story_beat == "entrance":
        negative += "، شلوغی بیش از حد"
    return {
        "asset_id": asset.get("asset_id"),
        "shot_id": asset.get("shot_id"),
        "kind": kind,
        "timeline_slot": asset.get("timeline_slot"),
        "prompt": "\n".join(lines),
        "negative": negative,
        "framing": framing,
        "usage_fa": "در ابزار تصویرساز paste کنید؛ character_ref را برای identity قفل کنید.",
    }


def _legacy_shot_row(asset_prompt: dict[str, Any], index: int) -> dict[str, str]:
    return {
        "id": f"shot_{index:02d}",
        "prompt": str(asset_prompt.get("prompt") or ""),
        "negative": str(asset_prompt.get("negative") or _DEFAULT_NEGATIVE),
        "usage_fa": str(asset_prompt.get("usage_fa") or ""),
        "asset_id": str(asset_prompt.get("asset_id") or ""),
    }


def run_prompt_craft_agent(
    spec: StudioSpec,
    *,
    cinematography: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    screenplay: dict[str, Any] | None = None,
    storyboard: dict[str, Any] | None = None,
    image_needs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build film + per-asset prompts; keep shot_XX rows for backward compatibility."""
    from agents.image_needs_agent import run_image_needs_agent

    appearance = ""
    try:
        appearance = spec.resolved_appearance_fa()
    except Exception:  # noqa: BLE001
        appearance = ""
    cine_by = {
        int(f.get("shot_id", i)): f
        for i, f in enumerate((cinematography or {}).get("frames") or [])
    }
    needs = image_needs or run_image_needs_agent(
        spec,
        screenplay=screenplay,
        storyboard=storyboard,
        character_appearance_fa=appearance or None,
    )
    # Enrich storyboard fields onto needs if missing
    enriched_assets: list[dict[str, Any]] = []
    for raw in needs.get("assets") or []:
        a = dict(raw)
        sid = a.get("shot_id")
        if sid is not None and not a.get("verb"):
            sb = _story_row(storyboard, int(sid))
            a["verb"] = sb.get("verb") or ""
            a["focal_point"] = a.get("focal_point") or sb.get("focal_point") or ""
        if appearance and not a.get("appearance_fa"):
            a["appearance_fa"] = appearance
        enriched_assets.append(a)

    asset_prompts: list[dict[str, Any]] = []
    for a in enriched_assets:
        sid = a.get("shot_id")
        sh = spec.shots[int(sid)] if sid is not None and int(sid) < len(spec.shots) else None
        cine = cine_by.get(int(sid)) if sid is not None else None
        asset_prompts.append(
            _prompt_asset(
                asset=a,
                sh=sh,
                spec=spec,
                cine_row=cine,
                appearance_fa=appearance,
            )
        )

    # Backward-compat: one prompt file per shot from keyframe asset
    shots_out: list[dict[str, str]] = []
    for i, _sh in enumerate(spec.shots):
        key = next(
            (
                p
                for p in asset_prompts
                if p.get("kind") == "keyframe" and p.get("shot_id") == i
            ),
            None,
        )
        if key is None:
            # fallback minimal
            key = next((p for p in asset_prompts if p.get("shot_id") == i), None)
        if key is None:
            continue
        shots_out.append(_legacy_shot_row(key, i))

    line_side = (continuity or {}).get("180_line_side") or "left"
    film_lines = [
        f"فیلم کوتاه 2D: «{spec.title}»",
        f"style={spec.style_id} grade={spec.grade} pace={spec.pace} emotion={spec.emotion}",
        f"continuity: 180-line={line_side} · aspect=16:9",
        f"assets={len(asset_prompts)} (see image_manifest.json)",
    ]
    if appearance:
        film_lines.append(f"کاراکتر قفل: {appearance}")
    if spec.character_id:
        film_lines.append(f"character_id={spec.character_id}")
    film_lines.extend(["", "توالی شات:"])
    for i, sh in enumerate(spec.shots):
        film_lines.append(f"- {i + 1}. {sh.action} ({sh.duration_sec}s)")
    film_lines.append("\nثبات شخصیت از character_ref؛ خط 180 در همه شات‌ها.")

    guide = (
        "# راهنمای پرامپت‌های تصویر (v2)\n\n"
        "- `image_manifest.json` → لیست دارایی + timeline_slot\n"
        "- `assets/asset_*.txt` → پرامپت هر دارایی\n"
        "- `shot_XX.txt` → فریم کلید شات (سازگاری عقب‌رو)\n"
        "- `shot_XX_motion.txt` → motion/I2V (AnimationPromptAgent)\n\n"
        "**Story عکس تولید نمی‌کند.** از character_ref برای identity استفاده کنید.\n"
    )
    return {
        "version": "2",
        "film_prompt": "\n".join(film_lines),
        "shots": shots_out,
        "assets": asset_prompts,
        "image_needs": needs,
        "guide_md": guide,
        "appearance_fa": appearance,
    }
