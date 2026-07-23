"""
AnimationPromptAgent — motion / I2V prompts for external animation tools.

Why: PromptCraftAgent targets still frames; motion tools need camera curve,
timing, pose verbs, and tool-specific phrasing from craft JSON + style catalog.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore


@lru_cache(maxsize=1)
def _motion_templates() -> dict[str, Any]:
    from libraries import load_library

    return load_library("prompts", "motion_templates.json")


def _style_line(spec: StudioSpec) -> str:
    try:
        from tools.style_catalog import get_style

        meta = get_style(spec.style_id) or {}
        traits = ", ".join(meta.get("prompt_traits") or [])[:120]
        name = meta.get("name") or spec.style_id
        return f"Style: {name} ({spec.style_id})" + (f" — {traits}" if traits else "")
    except Exception:  # noqa: BLE001
        return f"Style: {spec.style_id}, grade {spec.grade}"


def _camera_line(sh: ShotControl, cine: dict[str, Any], curve: dict[str, Any] | None) -> str:
    templates = _motion_templates()
    cam_id = str(cine.get("camera") or sh.camera or "static")
    verb = templates.get("camera_verbs", {}).get(cam_id, cam_id)
    size = cine.get("shot_size") or sh.shot_size or "MS"
    lens = cine.get("lens") or sh.lens
    light = cine.get("lighting") or sh.lighting
    parts = [verb, f"shot size {size}", f"lens {lens}", f"lighting {light}"]
    if curve and curve.get("keyframes"):
        kf = curve["keyframes"]
        parts.append(f"{len(kf)} camera keyframes @24fps")
    return ", ".join(parts)


def _motion_line(sh: ShotControl, timing: dict[str, Any] | None) -> str:
    templates = _motion_templates()
    pose = templates.get("pose_verbs", {}).get(sh.pose, sh.pose)
    beat = templates.get("beat_motion", {}).get(sh.story_beat, sh.story_beat)
    ant = int(sh.anticipation_frames)
    hold = int(sh.hold_frames)
    if timing:
        ant = int(timing.get("anticipation_frames") or ant)
        hold = int(timing.get("hold_frames") or hold)
    return (
        f"Pose: {pose}; beat: {beat}; "
        f"anticipation {ant}f → action → hold {hold}f; expression {sh.expression}"
    )


def _look_snippet(beat: str, grade: str) -> str:
    try:
        from tools.craft_packs import look_for_beat

        look = look_for_beat(beat, fallback_grade=grade)
        return f"grade `{look.get('gradeId')}` vignette {float(look.get('vignette', 0)):.2f}"
    except Exception:  # noqa: BLE001
        return f"grade `{grade}`"


def _shots_for_curves(
    spec: StudioSpec,
    cinematography: dict[str, Any] | None,
    timing: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    cine_by = {
        int(f.get("shot_id", i)): f
        for i, f in enumerate((cinematography or {}).get("frames") or [])
    }
    time_by = {
        int(t.get("shot_id", i)): t
        for i, t in enumerate((timing or {}).get("shots") or [])
    }
    rows: list[dict[str, Any]] = []
    for i, sh in enumerate(spec.shots):
        cine = cine_by.get(i, {})
        tim = time_by.get(i, {})
        try:
            from tools.craft_packs import camera_move_for_beat

            move = camera_move_for_beat(sh.story_beat, str(cine.get("camera") or sh.camera))
        except Exception:  # noqa: BLE001
            move = {"id": sh.camera}
        rows.append(
            {
                "shot_id": i,
                "duration_sec": sh.duration_sec,
                "duration_frames": max(12, int(round(sh.duration_sec * 24))),
                "anticipation_frames": tim.get("anticipation_frames", sh.anticipation_frames),
                "hold_frames": tim.get("hold_frames", sh.hold_frames),
                "camera": cine.get("camera") or sh.camera,
                "camera_move": move,
            }
        )
    return rows


def _render_tool_prompt(
    tool_id: str,
    *,
    spec: StudioSpec,
    sh: ShotControl,
    camera_line: str,
    motion_line: str,
    continuity_line: str,
) -> str:
    templates = _motion_templates()
    tool = (templates.get("tools") or {}).get(tool_id) or {}
    tpl = tool.get("shot_line") or "{action_line}. {camera_line}. {motion_line}."
    constraints = templates.get("constraints") or ""
    return tpl.format(
        title=spec.title,
        style_id=spec.style_id,
        style_line=_style_line(spec),
        action_line=sh.action.strip(),
        camera_line=camera_line,
        motion_line=motion_line,
        duration_sec=sh.duration_sec,
        continuity_line=continuity_line,
        constraints=constraints,
        emotion=spec.emotion,
        pace=spec.pace,
    ).strip()


def _motion_one(
    sh: ShotControl,
    index: int,
    spec: StudioSpec,
    *,
    cine: dict[str, Any],
    timing: dict[str, Any] | None,
    curve: dict[str, Any] | None,
    continuity: dict[str, Any] | None,
    tools: list[str],
) -> dict[str, Any]:
    line_side = (continuity or {}).get("180_line_side") or "left"
    continuity_line = f"180-degree line: look from {line_side}; {_look_snippet(sh.story_beat, spec.grade)}"
    camera_line = _camera_line(sh, cine, curve)
    motion_line = _motion_line(sh, timing)

    by_tool = {
        tid: _render_tool_prompt(
            tid,
            spec=spec,
            sh=sh,
            camera_line=camera_line,
            motion_line=motion_line,
            continuity_line=continuity_line,
        )
        for tid in tools
    }
    default_tool = _motion_templates().get("default_tool") or "generic"
    motion_prompt = by_tool.get(default_tool) or next(iter(by_tool.values()))

    motion_json: dict[str, Any] = {
        "shot_id": index,
        "beat": sh.story_beat,
        "duration_sec": sh.duration_sec,
        "fps": 24,
        "camera": cine.get("camera") or sh.camera,
        "pose": sh.pose,
        "expression": sh.expression,
        "anticipation_frames": int(
            (timing or {}).get("anticipation_frames") or sh.anticipation_frames
        ),
        "hold_frames": int((timing or {}).get("hold_frames") or sh.hold_frames),
        "camera_curve": curve,
        "continuity_180": line_side,
        "look": _look_snippet(sh.story_beat, spec.grade),
    }

    return {
        "id": f"shot_{index:02d}",
        "motion_prompt": motion_prompt,
        "motion_json": motion_json,
        "by_tool": by_tool,
        "usage_fa": "این پرامپت motion را در ابزار I2V/ویدیوی خارجی paste کنید — Story ویدیو نمی‌سازد.",
    }


def run_animation_prompt_agent(
    spec: StudioSpec,
    *,
    storyboard: dict[str, Any] | None = None,
    cinematography: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Build per-shot motion prompts + tool variants + film-level motion brief."""
    _ = storyboard
    templates = _motion_templates()
    tool_ids = tools or list((templates.get("tools") or {}).keys())
    if not tool_ids:
        tool_ids = ["generic"]

    curve_rows = _shots_for_curves(spec, cinematography, timing)
    try:
        from agents.camera_curve_agent import run_camera_curve_agent

        curves = run_camera_curve_agent(curve_rows, fps=24)
        curve_by = {int(c["shot_id"]): c for c in curves.get("shots") or []}
    except Exception:  # noqa: BLE001
        curve_by = {}

    cine_by = {
        int(f.get("shot_id", i)): f
        for i, f in enumerate((cinematography or {}).get("frames") or [])
    }
    time_by = {
        int(t.get("shot_id", i)): t
        for i, t in enumerate((timing or {}).get("shots") or [])
    }

    shots = [
        _motion_one(
            sh,
            i,
            spec,
            cine=cine_by.get(i, {}),
            timing=time_by.get(i),
            curve=curve_by.get(i),
            continuity=continuity,
            tools=tool_ids,
        )
        for i, sh in enumerate(spec.shots)
    ]

    default_tool = templates.get("default_tool") or "generic"
    film_tpl = (templates.get("tools") or {}).get(default_tool, {}).get("film_header") or "Film: {title}"
    film_lines = [
        film_tpl.format(
            title=spec.title,
            style_id=spec.style_id,
            emotion=spec.emotion,
            pace=spec.pace,
        ),
        "",
    ]
    for i, sh in enumerate(spec.shots):
        film_lines.append(f"- Shot {i + 1} ({sh.duration_sec}s): {sh.action[:80]}")
    film_lines.append("")
    film_lines.append(_motion_templates().get("constraints") or "")

    guide = (
        "# راهنمای پرامپت‌های motion\n\n"
        "| فایل | نقش |\n|------|-----|\n"
        "| `shot_XX.txt` | فریم کلید (تصویر) |\n"
        "| `shot_XX_motion.txt` | motion/I2V (generic) |\n"
        "| `shot_XX_motion.json` | پارامتر ساخت‌یافته |\n"
        "| `tools/runway/`, `kling/`, `pika/` | نسخهٔ ابزار-محور |\n"
        "| `film_motion.txt` | نمای کل sequence |\n\n"
        "**Story ویدیو تولید نمی‌کند** — این پرامپت‌ها را در Runway/Kling/Pika یا I2V paste کنید.\n"
    )

    return {
        "version": "1",
        "default_tool": default_tool,
        "tools": tool_ids,
        "film_motion_prompt": "\n".join(film_lines),
        "shots": shots,
        "guide_md": guide,
    }
