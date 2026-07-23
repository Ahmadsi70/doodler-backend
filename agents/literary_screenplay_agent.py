"""
LiteraryScreenplayAgent — cinematic screenplay prose from spec + agent chain.

Why: ScreenplayAgent alone only echoes action lines; readers need sluglines,
camera/lighting context, VO formatting, and subtext before external render.
"""

from __future__ import annotations

from typing import Any

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore

_BEAT_FA = {
    "entrance": "ورود",
    "reveal": "افشا",
    "reaction": "واکنش",
    "conflict": "درگیری",
    "decision": "تصمیم",
    "quiet_hold": "مکث",
    "exit": "خروج",
}

_CAMERA_FA = {
    "static": "ثابت",
    "motivated_push": "نزدیک‌شدن انگیزه‌دار (push-in)",
    "pan_follow": "پان همراه شخصیت",
    "reveal_drift": "کشف با drift آرام",
}

_LIGHTING_FA = {
    "three_point": "سه‌نقطه‌ای نرم",
    "rim_accent": "rim light + کنتراست احساسی",
}

_SIZE_FA = {"WS": "Wide", "MS": "Medium", "CU": "Close-Up", "insert": "Insert"}

_ATMOS = {
    "entrance": "صدای محیط آرام؛ فضا تنفس می‌کند.",
    "reveal": "یک جزئیات ناگهان توجه را می‌گیرد.",
    "reaction": "زمان کمی کند می‌شود — واکنش مهم‌تر از حرکت است.",
    "conflict": "تضاد بصری یا احساسی تشدید می‌شود.",
    "decision": "مکث تصمیم؛ نگاه یا ژست ثابت می‌ماند.",
    "quiet_hold": "سکوت معنادار؛ hold طولانی‌تر.",
    "exit": "فضا خالی می‌شود؛ شخصیت از کادر خارج می‌شود.",
}


def _slugline(sh: ShotControl, index: int, *, location_hint: str) -> str:
    """INT/EXT slugline from beat and action heuristics."""
    action = (sh.action or "").lower()
    ext_kw = ("خارج", "آسمان", "خیابان", "بیرون", "فضای باز", "ریل", "ایستگاه")
    is_ext = any(k in action for k in ext_kw) or sh.story_beat in {"entrance", "exit"}
    prefix = "EXT." if is_ext else "INT."
    loc = location_hint or sh.title or f"مکان {index + 1}"
    tod = "سحر" if any(k in action for k in ("سحر", "صبح", "مه")) else "روز"
    if "شب" in action:
        tod = "شب"
    return f"{prefix} {loc} — {tod}"


def _camera_block(sh: ShotControl, cine: dict[str, Any] | None) -> str:
    cine = cine or {}
    cam = _CAMERA_FA.get(str(cine.get("camera") or sh.camera), sh.camera)
    size = _SIZE_FA.get(str(cine.get("shot_size") or sh.shot_size or "MS").upper(), "MS")
    lens = cine.get("lens") or sh.lens
    light = _LIGHTING_FA.get(str(cine.get("lighting") or sh.lighting), sh.lighting)
    return f"**دوربین:** {cam} · **اندازه:** {size} · **لنز:** {lens} · **نور:** {light}"


def _look_note(beat: str, grade: str) -> str:
    try:
        from tools.craft_packs import look_for_beat

        look = look_for_beat(beat, fallback_grade=grade)
        gid = look.get("gradeId") or grade
        vig = look.get("vignette")
        return f"**Look:** grade `{gid}` · vignette {vig:.2f}"
    except Exception:  # noqa: BLE001
        return f"**Look:** `{grade}`"


def _resolve_sfx(sh: ShotControl, sb: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer storyboard/breakdown SFX; else infer from action for silent narratives."""
    if sb.get("sfx"):
        return list(sb["sfx"])
    try:
        from agents.audio_cue_agent import load_audio_catalog
        from agents.sfx_plan import infer_sfx_events
        from tools.audio_cues import ensure_audio_cue_files

        ensure_audio_cue_files()
        cues = dict(load_audio_catalog().get("cues") or {})
        return infer_sfx_events(sh.action, beat=sh.story_beat, catalog_cues=cues)
    except Exception:  # noqa: BLE001
        return []


def _action_prose(sh: ShotControl, sb: dict[str, Any]) -> list[str]:
    lines = [sh.action.strip()]
    nq = sb.get("narrative_question")
    if nq:
        lines.append("")
        lines.append(f"*سؤال روایی:* {nq}")
    verb = sb.get("verb")
    focal = sb.get("focal_point")
    if verb or focal:
        bits = []
        if verb:
            bits.append(f"فعل محور: `{verb}`")
        if focal:
            bits.append(f"فوکوس: `{focal}`")
        lines.append("")
        lines.append(" · ".join(bits))
    atmos = _ATMOS.get(sh.story_beat)
    if atmos:
        lines.append("")
        lines.append(f"*{atmos.strip()}*")
    sfx = _resolve_sfx(sh, sb)
    if sfx:
        from agents.sfx_plan import format_sfx_md

        lines.append("")
        lines.append(format_sfx_md(sfx))
    return lines


def run_literary_screenplay_agent(
    spec: StudioSpec,
    *,
    storyboard: dict[str, Any] | None = None,
    cinematography: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    location_hint: str | None = None,
) -> dict[str, Any]:
    """Build literary screenplay markdown and enriched shot records."""
    sb_by_id = {
        int(s.get("shot_id", i)): s
        for i, s in enumerate((storyboard or {}).get("shots") or [])
    }
    cine_by_id = {
        int(f.get("shot_id", i)): f
        for i, f in enumerate((cinematography or {}).get("frames") or [])
    }
    line_side = (continuity or {}).get("180_line_side") or "left"
    loc = location_hint or spec.title

    md_lines = [
        f"# نمایشنامه — {spec.title}",
        "",
        f"**مدت:** ~{spec.runtime_seconds}s · **سبک:** {spec.style_id} · **حس:** {spec.emotion}",
        f"**خط ۱۸۰°:** نگاه از سمت {line_side}",
        "",
        "---",
        "",
    ]
    shots_out: list[dict[str, Any]] = []

    for i, sh in enumerate(spec.shots):
        beat_fa = _BEAT_FA.get(sh.story_beat, sh.story_beat)
        sb = sb_by_id.get(i, {})
        cine = cine_by_id.get(i, {})
        slug = _slugline(sh, i, location_hint=loc)
        heading = sh.title or f"صحنه {i + 1}"

        md_lines.extend(
            [
                f"## {i + 1}. {heading}",
                "",
                slug,
                "",
                _camera_block(sh, cine),
                _look_note(sh.story_beat, spec.grade),
                "",
                f"**Beat:** {beat_fa} · **مدت:** {sh.duration_sec}s",
                "",
            ]
        )
        md_lines.extend(_action_prose(sh, sb))
        md_lines.append("")
        if sh.dialogue:
            dlg = sh.dialogue.strip()
            if dlg.startswith("(") and dlg.endswith(")"):
                md_lines.extend([f"> {dlg}", ""])
            else:
                md_lines.extend([f"**{sh.title or 'شخصیت'}**", f"> {dlg}", ""])
        md_lines.extend(["---", ""])

        sfx = _resolve_sfx(sh, sb)
        shots_out.append(
            {
                "index": i,
                "title": heading,
                "slugline": slug,
                "action": sh.action,
                "action_prose": "\n".join(_action_prose(sh, sb)),
                "dialogue": sh.dialogue or "",
                "duration_sec": sh.duration_sec,
                "beat": sh.story_beat,
                "beat_fa": beat_fa,
                "camera": cine.get("camera") or sh.camera,
                "lighting": cine.get("lighting") or sh.lighting,
                "shot_size": cine.get("shot_size") or sh.shot_size,
                "narrative_question": sb.get("narrative_question") or "",
                "sfx": sfx,
            }
        )

    md_lines.extend(["## Logline (brief)", "", spec.to_brief()])
    return {
        "version": "2",
        "literary": True,
        "title": spec.title,
        "shot_count": len(spec.shots),
        "shots": shots_out,
        "screenplay_md": "\n".join(md_lines),
    }
