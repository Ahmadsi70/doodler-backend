"""
Story-only job pipeline — standalone at ``C:\\Users\\badri\\Story``.

2D stack: Light draft / Remotion Pro. Williams TS for timing. No Blender.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

EventFn = Callable[[str, Any], None]
KIND = "studio_story"


def _emit(on_event: EventFn | None, kind: str, payload: Any) -> None:
    if on_event is not None:
        on_event(kind, payload)


def readiness_probe() -> dict[str, Any]:
    from tools.remotion_emitter import remotion_ready
    from tools.studio_profiles import find_ffmpeg, find_node
    from tools.williams_paths import williams_status

    ff = find_ffmpeg()
    rem = remotion_ready()
    williams = williams_status()
    report: dict[str, Any] = {
        "ok": True,
        "ffmpeg": bool(ff),
        "ffmpeg_path": ff,
        "node": bool(find_node()),
        "remotion": rem,
        "williams": williams,
        "manim": False,
        "blender": False,
        "errors": [],
        "warnings": [],
    }
    if not report["ffmpeg"]:
        report["warnings"].append(
            "FFmpeg not on PATH — external slideshow engine only."
        )
    if not rem:
        report["warnings"].append(
            "Remotion not installed — export still works; run remotion externally."
        )
    if not williams.get("ready"):
        report["warnings"].append(
            "Williams rules path missing — Node enrich falls back. "
            "Set WILLIAMS_RULES_PATH or vendor/williams-animation-rules"
        )
    return report


def run_story_job(
    prompt: str,
    job_id: str,
    extras: dict[str, Any] | None = None,
    *,
    on_event: EventFn | None = None,
) -> dict[str, Any]:
    from tools.job_status import write_job_status
    from tools.job_workspace import job_workspace
    from tools.render_profiles import get_render_profile, write_render_profile
    from tools.studio_profiles import readiness_for_kind
    from tools.style_catalog import merge_style_into_extras, write_style_profile

    extras = dict(extras or {})
    workspace = job_workspace(job_id)

    def _status(
        status: str,
        *,
        phase: str = "",
        error: str | None = None,
        log_line: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        write_job_status(
            workspace,
            job_id=job_id,
            status=status,
            kind=KIND,
            phase=phase,
            error=error,
            artifacts=artifacts,
            extras={
                k: extras.get(k)
                for k in ("quality", "style_id", "runtime_seconds")
                if k in extras
            },
            log_line=log_line,
        )

    try:
        _status("running", phase="Starting Story", log_line=f"job start id={job_id}")
        _emit(on_event, "job_meta", {"job_id": job_id, "job_out_dir": str(workspace)})

        probe = readiness_probe()
        ok, kind_errs = readiness_for_kind(probe, KIND)
        if not ok:
            raise RuntimeError("; ".join(kind_errs))

        quality = str(extras.get("quality") or "light")
        os.environ["RENDER_QUALITY"] = quality
        os.environ["RENDER_STUDIO"] = KIND
        os.environ["STORY_SLIDE_STYLE"] = "story"
        os.environ["COMMERCIAL_SLIDE_STYLE"] = "story"

        extras = merge_style_into_extras(extras, KIND)
        resolved = extras.get("style_resolved") or {}
        if resolved:
            write_style_profile(workspace, resolved)
            _emit(on_event, "log", f"style_profile {resolved.get('style_id')}")

        try:
            prof = get_render_profile(KIND, quality)
            write_render_profile(
                workspace,
                prof,
                extra={"job_id": job_id, "kind": KIND, "style_id": extras.get("style_id")},
            )
        except Exception as prof_exc:  # noqa: BLE001
            _emit(on_event, "log", f"render_profile warn: {prof_exc!r}")

        char = extras.get("character_main") or extras.get("character_path")
        if char:
            extras["character_main"] = char

        _emit(on_event, "phase", "LangGraph studio pipeline…")
        _status("running", phase="StudioGraph")

        from tools.studio_graph import run_brief_studio_graph

        graph_out = run_brief_studio_graph(
            prompt,
            workspace,
            extras=extras,
            style_profile=resolved if isinstance(resolved, dict) else None,
            max_revision_passes=int(extras.get("max_revision_passes") or 2),
        )
        chain_dict = graph_out.get("chain") or {}
        supervisor_dict = graph_out.get("supervisor") or {}
        _emit(
            on_event,
            "log",
            f"StudioGraph ok={graph_out.get('ok')} revision={graph_out.get('revision_passes')} "
            f"supervisor_passed={supervisor_dict.get('passed')}",
        )
        for line in graph_out.get("logs") or []:
            _emit(on_event, "log", line)

        if not graph_out.get("ok"):
            raise RuntimeError(graph_out.get("error") or "studio graph export failed")

        result_artifacts = dict(graph_out.get("artifacts") or {})
        result_artifacts.setdefault("ok", True)
        export_only = not bool(extras.get("render"))
        result_artifacts.setdefault("export_only", export_only)
        result_artifacts.setdefault("style_id", extras.get("style_id"))
        result_artifacts.setdefault("agents_dir", str(Path(workspace) / "agents"))

        # Surface render result if present
        render_result = graph_out.get("render_result") or result_artifacts.get("render")
        if render_result:
            result_artifacts["render"] = render_result
            if render_result.get("render_mp4"):
                result_artifacts["render_mp4"] = render_result["render_mp4"]
            if render_result.get("code_dir"):
                result_artifacts["render_code_dir"] = render_result["code_dir"]
        try:
            from tools.rebuild_pack import write_rebuild_pack
        except ImportError:
            from .rebuild_pack import write_rebuild_pack

        result_artifacts["rebuild"] = write_rebuild_pack(
            workspace,
            brief=prompt,
            artifacts=result_artifacts,
            extras=extras,
        )
        _emit(on_event, "artifacts", result_artifacts)
        _status(
            "succeeded",
            phase="Done",
            artifacts=result_artifacts,
            log_line=f"export: {result_artifacts.get('export_root')}",
        )
        return {
            "ok": True,
            "exported": True,
            "job_id": job_id,
            "job_out_dir": str(workspace.resolve()),
            "kind": KIND,
            "artifacts": result_artifacts,
        }
    except Exception as exc:
        _status("failed", phase="Failed", error=str(exc), log_line=f"error: {exc}")
        _emit(on_event, "error", str(exc))
        raise
