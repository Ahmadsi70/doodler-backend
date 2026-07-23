"""
Act-batch render — render each ActSlice then concat to one film.

Why: 10 min Remotion jobs risk timeout/OOM; acts stay inspectable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from studio_spec import StudioSpec

EventFn = Callable[[str, Any], None] | None

# Late-bound for monkeypatch in tests
try:
    from tools.studio_api import render_from_spec
except ImportError:
    from .studio_api import render_from_spec  # type: ignore

try:
    from tools.act_planner import chunk_spec_by_acts, plan_acts
except ImportError:
    from .act_planner import chunk_spec_by_acts, plan_acts  # type: ignore

try:
    from tools.chapter_concat import concat_mp4s
except ImportError:
    from .chapter_concat import concat_mp4s  # type: ignore

try:
    from tools.studio_profiles import find_ffmpeg
except ImportError:
    from .studio_profiles import find_ffmpeg  # type: ignore


def render_spec_by_acts(
    spec: StudioSpec,
    *,
    workspace: Path | str,
    target_act_seconds: float | None = None,
    job_id: str | None = None,
    on_event: EventFn = None,
) -> dict[str, Any]:
    """
    Render each act into ``acts/act-N/render.mp4``, concat → ``render.mp4``.
    """
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    plan = plan_acts(spec, target_act_seconds=target_act_seconds)
    chunks = chunk_spec_by_acts(spec, plan)
    acts_dir = root / "acts"
    acts_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    act_results: list[dict[str, Any]] = []

    def _emit(kind: str, payload: Any) -> None:
        if on_event:
            on_event(kind, payload)

    for act, chunk in zip(plan.acts, chunks):
        act_ws = acts_dir / act.id
        _emit("phase", f"Render {act.title} ({act.id})…")
        res = render_from_spec(
            chunk,
            job_id=f"{job_id or root.name}-{act.id}",
            workspace=act_ws,
            on_event=on_event,
        )
        act_results.append({"act": act.to_public_dict(), "result": res})
        mp4 = Path((res.get("artifacts") or {}).get("render_mp4") or (act_ws / "render.mp4"))
        if not res.get("ok") or not mp4.is_file():
            return {
                "ok": False,
                "error": f"act render failed: {act.id} — {res.get('error')}",
                "act_count": len(plan.acts),
                "act_results": act_results,
                "artifacts": {},
            }
        parts.append(mp4)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {
            "ok": False,
            "error": "FFmpeg required to concat act renders",
            "act_count": len(plan.acts),
            "act_results": act_results,
            "artifacts": {"act_parts": [str(p) for p in parts]},
        }

    final = root / "render.mp4"
    concat_mp4s(parts, final, ffmpeg=ffmpeg)
    (root / "act_plan.json").write_text(
        __import__("json").dumps(plan.to_public_dict(), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    _emit("phase", "Acts concatenated")
    return {
        "ok": True,
        "rendered": True,
        "act_count": len(plan.acts),
        "act_results": act_results,
        "artifacts": {
            "render_mp4": str(final.resolve()),
            "act_parts": [str(p) for p in parts],
            "act_plan": str((root / "act_plan.json").resolve()),
        },
        "notes": [f"acts={len(plan.acts)}"],
    }
