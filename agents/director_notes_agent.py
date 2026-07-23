"""
DirectorNotesAgent — plain-language construction notes per shot.

Why: non-technical users understand what each code/prompt block will do externally.
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
_POSE_FA = {"idle": "ایستاده", "walk": "راه‌رفتن", "react": "واکنش", "run": "دویدن"}
_CAMERA_FA = {
    "static": "ثابت",
    "motivated_push": "نزدیک‌شدن انگیزه‌دار",
    "pan_follow": "پان همراه",
    "reveal_drift": "کشف با drift",
}


def _note_one(sh: ShotControl, index: int, *, continuity: dict[str, Any] | None) -> dict[str, str]:
    beat = _BEAT_FA.get(sh.story_beat, sh.story_beat)
    pose = _POSE_FA.get(sh.pose, sh.pose)
    cam = _CAMERA_FA.get(sh.camera, sh.camera)
    line_side = (continuity or {}).get("180_line_side") or "left"
    body = (
        f"در شات {index + 1}، بیننده {sh.action} "
        f"این beat ({beat}) را در {sh.duration_sec} ثانیه می‌بیند. "
        f"دوربین {cam} است؛ شخصیت {pose} با حالت {sh.expression}. "
        f"آنتسیپیشن {sh.anticipation_frames}f و hold {sh.hold_frames}f (@24fps). "
        f"خط ۱۸۰°: نگاه از سمت {line_side}."
    )
    if sh.dialogue:
        body += f" دیالوگ: «{sh.dialogue}»."
    code_hint = (
        "در کد remotion این شات → `story_props.json` shots[] با camera/pose/timing; "
        "پرامپت تصویر → `prompts/shot_XX.txt` (خود ابزار عکس نمی‌سازد)."
    )
    return {
        "index": str(index),
        "title": sh.title or f"شات {index}",
        "body_fa": body,
        "code_hint_fa": code_hint,
        "camera_fa": cam,
        "beat_fa": beat,
    }


def run_director_notes_agent(
    spec: StudioSpec,
    *,
    continuity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Director-facing explanation markdown and per-shot notes."""
    shot_notes = [_note_one(sh, i, continuity=continuity) for i, sh in enumerate(spec.shots)]
    lines = [
        f"# توضیح ساخت — {spec.title}",
        "",
        "این سند قبل از رندر خارجی بخوانید. Story هیچ عکس/ویدیویی نمی‌سازد.",
        "",
        "## خلاصه",
        "",
        f"- **{len(spec.shots)}** شات · ~**{spec.runtime_seconds}** ثانیه",
        f"- حس: **{spec.emotion}** · grade: **{spec.grade}**",
        "- بعد از Approve، بسته در `export/` آمادهٔ copy به ابزار خارجی است.",
        "",
    ]
    for note in shot_notes:
        lines.extend(
            [
                f"### شات {int(note['index']) + 1}: {note['title']}",
                "",
                note["body_fa"],
                "",
                f"*{note['code_hint_fa']}*",
                "",
            ]
        )
    return {
        "version": "1",
        "shot_notes": shot_notes,
        "explanation_md": "\n".join(lines),
    }
