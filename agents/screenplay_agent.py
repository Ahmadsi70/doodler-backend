"""
ScreenplayAgent — literary screenplay + structured JSON from StudioSpec.

Why: users approve story on readable script before external render, not raw tables only.
"""

from __future__ import annotations

from typing import Any

try:
    from studio_spec import StudioSpec
except ImportError:
    from ..studio_spec import StudioSpec  # type: ignore


_BEAT_FA = {
    "entrance": "ورود",
    "reveal": "افشا",
    "reaction": "واکنش",
    "conflict": "درگیری",
    "decision": "تصمیم",
    "quiet_hold": "مکث",
    "exit": "خروج",
}


def run_screenplay_agent(
    spec: StudioSpec,
    *,
    storyboard: dict[str, Any] | None = None,
    cinematography: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    literary: bool = True,
) -> dict[str, Any]:
    """Build screenplay markdown; uses LiteraryScreenplayAgent when cine data exists."""
    if literary and cinematography is not None:
        from agents.literary_screenplay_agent import run_literary_screenplay_agent

        return run_literary_screenplay_agent(
            spec,
            storyboard=storyboard,
            cinematography=cinematography,
            continuity=continuity,
        )

    sb_by_id = {
        int(s.get("shot_id", i)): s
        for i, s in enumerate((storyboard or {}).get("shots") or [])
    }
    shots_out: list[dict[str, Any]] = []
    md_lines = [
        f"# نمایشنامه — {spec.title}",
        "",
        f"**مدت:** ~{spec.runtime_seconds}s · **سبک:** {spec.style_id} · **حس:** {spec.emotion}",
        "",
        "---",
        "",
    ]
    for i, sh in enumerate(spec.shots):
        beat_fa = _BEAT_FA.get(sh.story_beat, sh.story_beat)
        sb = sb_by_id.get(i, {})
        heading = sh.title or f"شات {i + 1}"
        md_lines.extend(
            [
                f"## صحنه {i + 1} — {heading}",
                "",
                f"**Beat:** {beat_fa} · **مدت:** {sh.duration_sec}s",
                "",
                sh.action,
                "",
            ]
        )
        if sh.dialogue:
            md_lines.extend([f"**دیالوگ:** «{sh.dialogue}»", ""])
        sfx = list(sb.get("sfx") or [])
        if not sfx:
            try:
                from agents.audio_cue_agent import load_audio_catalog
                from agents.sfx_plan import infer_sfx_events
                from tools.audio_cues import ensure_audio_cue_files

                ensure_audio_cue_files()
                sfx = infer_sfx_events(
                    sh.action,
                    beat=sh.story_beat,
                    catalog_cues=dict(load_audio_catalog().get("cues") or {}),
                )
            except Exception:  # noqa: BLE001
                sfx = []
        if sfx:
            from agents.sfx_plan import format_sfx_md

            md_lines.extend([format_sfx_md(sfx), ""])
        md_lines.append("---")
        md_lines.append("")
        shots_out.append(
            {
                "index": i,
                "title": heading,
                "action": sh.action,
                "dialogue": sh.dialogue or "",
                "duration_sec": sh.duration_sec,
                "beat": sh.story_beat,
                "beat_fa": beat_fa,
                "camera": sh.camera,
                "pose": sh.pose,
                "expression": sh.expression,
                "narrative_question": sb.get("narrative_question") or "",
                "sfx": sfx,
            }
        )
    md_lines.extend(["## متن پیوسته (brief)", "", spec.to_brief()])
    return {
        "version": "1",
        "literary": False,
        "title": spec.title,
        "shot_count": len(spec.shots),
        "shots": shots_out,
        "screenplay_md": "\n".join(md_lines),
    }
