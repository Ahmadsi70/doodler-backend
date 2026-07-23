"""
LangGraph studio orchestrator — craft supervision loop + export gate + human approve.

Why: replace imperative while-loops with explicit conditional edges, checkpoint-ready
state, and a single export path for brief jobs and Director Board approvals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from tools.studio_job_state import (
    StudioJobState,
    append_log,
    has_approve_interrupt,
    has_interrupt,
    has_screenplay_interrupt,
)

GraphMode = Literal["brief", "spec"]

_LANGGRAPH_AVAILABLE = False
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph
    from langgraph.types import Command, interrupt

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    MemorySaver = None  # type: ignore[misc, assignment]
    StateGraph = None  # type: ignore[misc, assignment]
    END = "__end__"
    Command = None  # type: ignore[misc, assignment]

    def interrupt(_payload):  # type: ignore[misc]
        raise RuntimeError("langgraph not installed")


def langgraph_available() -> bool:
    return _LANGGRAPH_AVAILABLE


def director_thread_id(job_dir: Path | str) -> str:
    """Stable LangGraph thread id per job workspace."""
    return f"{Path(job_dir).name}-director"


def _graph_config(job_dir: Path | str, *, thread_id: str | None = None) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id or director_thread_id(job_dir)}}


def _save_checkpoint(job_path: Path, name: str, state: StudioJobState) -> None:
    ckpt = job_path / "checkpoints" / name
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _finalize_state(state: StudioJobState) -> StudioJobState:
    out = dict(state)
    interrupted = has_interrupt(out)
    out["awaiting_screenplay"] = has_screenplay_interrupt(out)
    out["awaiting_approve"] = has_approve_interrupt(out) or (
        interrupted and not out["awaiting_screenplay"]
    )
    if interrupted:
        if out["awaiting_screenplay"]:
            out["phase"] = "await_screenplay"
        elif out["awaiting_approve"]:
            out["phase"] = "await_approve"
    elif out.get("awaiting_approve") and not out.get("phase"):
        out["phase"] = "await_approve"
    return out  # type: ignore[return-value]


def _node_draft_screenplay(state: StudioJobState) -> StudioJobState:
    from agents.story_chain import run_draft_screenplay_phase

    brief = state.get("brief") or ""
    job_dir = Path(state["job_dir"])
    extras = dict(state.get("extras") or {})
    screenplay = run_draft_screenplay_phase(brief, job_dir, extras=extras)
    return {
        "screenplay": screenplay,
        "phase": "draft_screenplay",
        "logs": append_log(
            state,
            f"draft_screenplay scenes={screenplay.get('scene_count', 0)}",
        ),
    }


def _node_await_screenplay(state: StudioJobState) -> StudioJobState:
    """Human gate — approve draft screenplay before storyboard craft."""
    extras = dict(state.get("extras") or {})
    if extras.get("skip_screenplay_gate") or state.get("screenplay_approved"):
        return {
            "screenplay_approved": True,
            "awaiting_screenplay": False,
            "phase": "screenplay_approved",
            "logs": append_log(state, "await_screenplay skipped"),
        }
    sp = dict(state.get("screenplay") or {})
    payload = interrupt(
        {
            "kind": "await_screenplay",
            "message_fa": "تأیید پیش‌نویس سناریو قبل از storyboard.",
            "screenplay_md": sp.get("screenplay_md"),
            "job_dir": state.get("job_dir"),
        }
    )
    approved = False
    sp_update: dict[str, Any] | None = None
    if isinstance(payload, dict):
        approved = bool(payload.get("screenplay_approved") or payload.get("approved"))
        sp_update = payload.get("screenplay")
    else:
        approved = bool(payload)
    out: StudioJobState = {
        "screenplay_approved": approved,
        "awaiting_screenplay": False,
        "phase": "screenplay_approved" if approved else "screenplay_denied",
        "logs": append_log(state, f"await_screenplay resume approved={approved}"),
    }
    if sp_update:
        out["screenplay"] = sp_update
        agents = Path(state["job_dir"]) / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "draft_screenplay.json").write_text(
            json.dumps(sp_update, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if not approved:
        out["ok"] = False
        out["error"] = "Screenplay not approved"
    return out


def _route_after_screenplay(state: StudioJobState) -> str:
    return "craft" if state.get("screenplay_approved") else "blocked"


def _node_screenplay_blocked(state: StudioJobState) -> StudioJobState:
    return {
        "ok": False,
        "error": state.get("error") or "Screenplay not approved",
        "phase": "screenplay_blocked",
        "logs": append_log(state, "craft blocked at await_screenplay"),
    }


def _node_craft_visual(state: StudioJobState) -> StudioJobState:
    from agents.story_chain import run_craft_from_screenplay

    brief = state.get("brief") or ""
    job_dir = Path(state["job_dir"])
    extras = dict(state.get("extras") or {})
    extras.setdefault("quality_gate_strict", False)
    screenplay = dict(state.get("screenplay") or {})
    chain = run_craft_from_screenplay(brief, job_dir, screenplay, extras=extras)
    return {
        "chain": chain.to_dict(),
        "phase": "craft_done",
        "ok": bool(chain.ok),
        "logs": append_log(
            state,
            f"craft_visual ok={chain.ok} shots={len(chain.storyboard.get('shots') or [])}",
        ),
    }


def _node_craft_chain(state: StudioJobState) -> StudioJobState:
    from agents.story_chain import run_story_agent_chain

    brief = state.get("brief") or ""
    job_dir = Path(state["job_dir"])
    extras = dict(state.get("extras") or {})
    extras.setdefault("quality_gate_strict", False)
    chain = run_story_agent_chain(brief, job_dir, extras=extras)
    return {
        "chain": chain.to_dict(),
        "phase": "craft_done",
        "logs": append_log(state, f"craft ok={chain.ok} shots={len(chain.storyboard.get('shots') or [])} phase=screenplay_breakdown"),
    }


def _node_supervisor(state: StudioJobState) -> StudioJobState:
    from agents.story_chain import StoryChainResult, _load_job_scene_ir
    from agents.story_supervisor import run_story_supervisor

    brief = state.get("brief") or ""
    job_dir = Path(state["job_dir"])
    extras = dict(state.get("extras") or {})
    chain = StoryChainResult(**dict(state.get("chain") or {}))
    sup = run_story_supervisor(
        _load_job_scene_ir(brief, job_dir),
        brief=brief,
        extras=extras,
        style_profile=state.get("style_profile"),
        job_dir=job_dir,
        continuity=chain.continuity,
        strict=False,
    )
    return {
        "supervisor": sup.to_dict(),
        "phase": "supervised",
        "logs": append_log(
            state,
            f"supervisor passed={sup.passed} score={sup.score} target={sup.revision_target}",
        ),
    }


def _route_after_supervisor(state: StudioJobState) -> str:
    sup = state.get("supervisor") or {}
    if sup.get("passed"):
        return "export"
    max_p = int(state.get("max_revision_passes") or 2)
    rev = int(state.get("revision_passes") or 0)
    if rev < max_p and sup.get("revision_target"):
        return "revise"
    return "export"


def _route_after_supervisor_craft(state: StudioJobState) -> str:
    """Craft-only graph: stop after supervise/revise — no export."""
    sup = state.get("supervisor") or {}
    if sup.get("passed"):
        return "done"
    max_p = int(state.get("max_revision_passes") or 2)
    rev = int(state.get("revision_passes") or 0)
    if rev < max_p and sup.get("revision_target"):
        return "revise"
    return "done"


def _node_craft_complete(state: StudioJobState) -> StudioJobState:
    chain = state.get("chain") or {}
    shots = (chain.get("storyboard") or {}).get("shots") or []
    ok = bool(shots)
    return {
        "ok": ok,
        "phase": "craft_complete",
        "error": "" if ok else "craft produced no shots",
        "logs": append_log(state, f"craft_complete ok={ok} shots={len(shots)}"),
    }


def _node_revise(state: StudioJobState) -> StudioJobState:
    from agents.story_chain import StoryChainResult, revise_for_target

    brief = state.get("brief") or ""
    chain = StoryChainResult(**dict(state.get("chain") or {}))
    target = str((state.get("supervisor") or {}).get("revision_target") or "")
    chain = revise_for_target(brief, chain, target, fps=24)
    rev = int(state.get("revision_passes") or 0) + 1
    return {
        "chain": chain.to_dict(),
        "revision_passes": rev,
        "phase": "revised",
        "logs": append_log(state, f"revision #{rev} target={target}"),
    }


def _node_await_approve(state: StudioJobState) -> StudioJobState:
    """Human-in-the-loop gate — interrupt until Director approves export."""
    if state.get("approved"):
        return {
            "awaiting_approve": False,
            "phase": "approved",
            "logs": append_log(state, "await_approve skipped (already approved)"),
        }
    payload = interrupt(
        {
            "kind": "await_approve",
            "message_fa": "تأیید کارگردان لازم است قبل از صدور بسته.",
            "job_dir": state.get("job_dir"),
        }
    )
    approved = False
    spec_update: dict[str, Any] | None = None
    if isinstance(payload, dict):
        approved = bool(payload.get("approved"))
        spec_update = payload.get("spec")
    else:
        approved = bool(payload)
    out: StudioJobState = {
        "approved": approved,
        "awaiting_approve": False,
        "phase": "approved" if approved else "approve_denied",
        "logs": append_log(state, f"await_approve resume approved={approved}"),
    }
    if spec_update:
        out["spec"] = spec_update
    if not approved:
        out["ok"] = False
        out["error"] = "Design not approved"
    return out


def _route_after_approve(state: StudioJobState) -> str:
    return "export" if state.get("approved") else "blocked"


def _node_blocked(state: StudioJobState) -> StudioJobState:
    return {
        "ok": False,
        "error": state.get("error") or "Design not approved",
        "phase": "export_blocked",
        "logs": append_log(state, "export blocked at await_approve"),
    }


def _export_targets(state: StudioJobState) -> list[str]:
    if state.get("targets"):
        return list(state["targets"])
    quality = str((state.get("extras") or {}).get("quality") or "light").lower()
    if quality == "pro":
        return ["prompts", "remotion"]
    if quality == "light":
        return ["prompts", "slideshow"]
    return ["prompts", "remotion", "slideshow"]


def _node_export(state: StudioJobState) -> StudioJobState:
    from tools.animation_export import export_animation_bundle, spec_from_chain
    from tools.studio_api import export_from_spec
    from studio_spec import StudioSpec

    job_dir = Path(state["job_dir"])
    targets = _export_targets(state)
    mode = state.get("mode") or "brief"

    if mode == "spec":
        spec = StudioSpec.model_validate(state["spec"])
        if not state.get("approved"):
            return {
                "ok": False,
                "error": "Design not approved",
                "phase": "export_blocked",
                "logs": append_log(state, "export blocked: not approved"),
            }
        result = export_from_spec(
            spec.model_copy(update={"mode": "direct"}),
            workspace=job_dir,
            targets=targets,
        )
        bundle = {
            "ok": result.get("ok"),
            "export_root": (result.get("artifacts") or {}).get("export_root"),
            "manifest": (result.get("artifacts") or {}).get("manifest"),
        }
        gate_path = job_dir / "export" / "export_gate.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.is_file() else {}
        return {
            "bundle": bundle,
            "gate": gate,
            "artifacts": result.get("artifacts") or {},
            "ok": bool(result.get("ok") and gate.get("ok", True)),
            "error": "" if result.get("ok") else str(result.get("error") or "export failed"),
            "phase": "exported",
            "targets": targets,
            "awaiting_approve": False,
            "logs": append_log(state, f"export spec ok={result.get('ok')}"),
        }

    from agents.story_chain import StoryChainResult

    extras = dict(state.get("extras") or {})
    chain = StoryChainResult(**dict(state.get("chain") or {}))
    resolved = state.get("style_profile") or {}
    char = extras.get("character_main") or extras.get("character_path")
    export_spec = spec_from_chain(
        chain,
        title=str(extras.get("title") or (state.get("brief") or "")[:48] or "Story"),
        quality=str(extras.get("quality") or "light"),
        runtime_seconds=float(extras.get("runtime_seconds") or 60.0),
        character_path=str(char) if char else None,
        style_id=str(extras.get("style_id") or "symmetrical_pastel_cinema"),
        grade=str((resolved.get("engine") or {}).get("grade") or "pastel_muted"),
        emotion=str(extras.get("emotion") or "neutral"),
    )
    bundle = export_animation_bundle(export_spec, job_dir / "export", targets=targets)  # type: ignore[arg-type]
    gate_path = job_dir / "export" / "export_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.is_file() else {}
    ok = bool(bundle.get("ok") and gate.get("ok", True))
    extras = dict(state.get("extras") or {})
    export_only = not bool(extras.get("render") or state.get("render_requested"))
    artifacts = {
        "export_root": bundle.get("export_root"),
        "manifest": bundle.get("manifest"),
        "screenplay": bundle.get("screenplay"),
        "explanation": bundle.get("explanation"),
        "agents_dir": chain.agents_dir,
        "export_only": export_only,
    }
    return {
        "bundle": bundle,
        "gate": gate,
        "artifacts": artifacts,
        "ok": ok,
        "error": "" if ok else str(bundle.get("error") or gate.get("missing") or "gate failed"),
        "phase": "exported",
        "targets": targets,
        "awaiting_approve": False,
        "logs": append_log(state, f"export brief ok={ok}"),
    }


def _node_gate(state: StudioJobState) -> StudioJobState:
    gate = dict(state.get("gate") or {})
    ok = bool(state.get("ok")) and bool(gate.get("ok", True))
    err = state.get("error") or ""
    if not ok and not err:
        err = f"export gate failed: {gate.get('missing')}"
    return {
        "ok": ok,
        "error": err,
        "phase": "gate_pass" if ok else "gate_fail",
        "awaiting_approve": False,
        "logs": append_log(state, f"gate ok={ok}"),
    }


def _node_render(state: StudioJobState) -> StudioJobState:
    """Phase E — render to MP4 or generate ready-to-run code."""
    from agents.render_agent import RenderResult, run_render_agent

    job_dir = Path(state["job_dir"])
    export_dir = job_dir / "export"
    if not export_dir.is_dir():
        export_dir = job_dir
    extras = dict(state.get("extras") or {})
    quality = str(extras.get("quality") or "light")
    render_mode = state.get("render_mode") or (
        "direct_render" if extras.get("render") else "code_only"
    )

    # Try to find story_props.json — check export dir, then remotion/public
    props_path = export_dir / "story_props.json"
    if not props_path.is_file():
        from pathlib import Path as _Path
        alt = _Path(__file__).resolve().parents[1] / "remotion" / "public" / "story_props.json"
        if alt.is_file():
            # Copy to job dir so render agent can find it
            import shutil as _shutil
            export_dir.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(alt, export_dir / "story_props.json")

    result: RenderResult = run_render_agent(
        export_dir,
        mode=render_mode,  # type: ignore[arg-type]
        quality=quality,
        title=str(extras.get("title") or (state.get("brief") or "Story")[:48] or "Story"),
        timeout_sec=float(extras.get("render_timeout_sec") or 900.0),
    )

    render_dict: dict[str, Any] = {
        "ok": result.ok,
        "backend": result.backend,
        "render_mp4": result.render_mp4,
        "code_dir": result.code_dir,
        "code_files": result.code_files,
        "run_command": result.run_command,
        "error": result.error,
        "logs": result.logs,
    }

    artifacts = dict(state.get("artifacts") or {})
    artifacts["render"] = render_dict
    artifacts["export_only"] = render_mode != "direct_render"
    if result.render_mp4:
        artifacts["render_mp4"] = result.render_mp4
    if result.code_dir:
        artifacts["render_code_dir"] = result.code_dir

    return {
        "render_result": render_dict,
        "artifacts": artifacts,
        "ok": result.ok and bool(state.get("ok")),
        "error": result.error or state.get("error") or "",
        "phase": "render_done" if result.ok else "render_failed",
        "render_requested": True,
        "logs": append_log(
            state,
            f"render mode={render_mode} backend={result.backend} ok={result.ok}",
        ),
    }


def _route_after_gate(state: StudioJobState) -> str:
    """Decide: proceed to render node, or end the graph."""
    if not state.get("ok"):
        return "end"
    extras = dict(state.get("extras") or {})
    if extras.get("render") or state.get("render_requested"):
        return "render"
    return "end"


def _build_brief_graph():
    g = StateGraph(StudioJobState)
    g.add_node("craft", _node_craft_chain)
    g.add_node("supervisor", _node_supervisor)
    g.add_node("revise", _node_revise)
    g.add_node("export", _node_export)
    g.add_node("gate", _node_gate)
    g.add_node("render", _node_render)
    g.set_entry_point("craft")
    g.add_edge("craft", "supervisor")
    g.add_conditional_edges("supervisor", _route_after_supervisor, {"revise": "revise", "export": "export"})
    g.add_edge("revise", "supervisor")
    g.add_edge("export", "gate")
    g.add_conditional_edges("gate", _route_after_gate, {"render": "render", "end": END})
    g.add_edge("render", END)
    return g


def _build_brief_craft_graph():
    """Director design: draft → screenplay approve → visual craft → supervise."""
    g = StateGraph(StudioJobState)
    g.add_node("draft_screenplay", _node_draft_screenplay)
    g.add_node("await_screenplay", _node_await_screenplay)
    g.add_node("craft_visual", _node_craft_visual)
    g.add_node("blocked", _node_screenplay_blocked)
    g.add_node("supervisor", _node_supervisor)
    g.add_node("revise", _node_revise)
    g.add_node("complete", _node_craft_complete)
    g.set_entry_point("draft_screenplay")
    g.add_edge("draft_screenplay", "await_screenplay")
    g.add_conditional_edges(
        "await_screenplay",
        _route_after_screenplay,
        {"craft": "craft_visual", "blocked": "blocked"},
    )
    g.add_edge("craft_visual", "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_after_supervisor_craft,
        {"revise": "revise", "done": "complete"},
    )
    g.add_edge("revise", "supervisor")
    g.add_edge("complete", END)
    g.add_edge("blocked", END)
    return g


def _build_spec_graph():
    g = StateGraph(StudioJobState)
    g.add_node("await_approve", _node_await_approve)
    g.add_node("export", _node_export)
    g.add_node("gate", _node_gate)
    g.add_node("render", _node_render)
    g.add_node("blocked", _node_blocked)
    g.set_entry_point("await_approve")
    g.add_conditional_edges(
        "await_approve",
        _route_after_approve,
        {"export": "export", "blocked": "blocked"},
    )
    g.add_edge("export", "gate")
    g.add_conditional_edges("gate", _route_after_gate, {"render": "render", "end": END})
    g.add_edge("render", END)
    g.add_edge("blocked", END)
    return g


_compiled_brief: Any = None
_compiled_brief_craft: Any = None
_compiled_spec: Any = None


def _make_checkpointer():
    """Sqlite checkpoint for Colab resume; fallback MemorySaver."""
    if not _LANGGRAPH_AVAILABLE:
        return None
    import os
    import sqlite3

    base = Path(os.environ.get("STORY_CHECKPOINT_DIR", ".story/checkpoints"))
    base.mkdir(parents=True, exist_ok=True)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(base / "studio_graph.db"), check_same_thread=False)
        return SqliteSaver(conn)
    except Exception:  # noqa: BLE001
        return MemorySaver()


_memory = _make_checkpointer()


def _get_compiled(mode: GraphMode | Literal["brief_craft"]):
    global _compiled_brief, _compiled_brief_craft, _compiled_spec
    if not _LANGGRAPH_AVAILABLE:
        raise RuntimeError("langgraph not installed — pip install langgraph")
    if mode == "brief":
        if _compiled_brief is None:
            _compiled_brief = _build_brief_graph().compile(checkpointer=_memory)
        return _compiled_brief
    if mode == "brief_craft":
        if _compiled_brief_craft is None:
            _compiled_brief_craft = _build_brief_craft_graph().compile(checkpointer=_memory)
        return _compiled_brief_craft
    if _compiled_spec is None:
        _compiled_spec = _build_spec_graph().compile(checkpointer=_memory)
    return _compiled_spec


def run_brief_craft_graph(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    max_revision_passes: int = 2,
    thread_id: str | None = None,
    on_phase: Any | None = None,
) -> StudioJobState:
    """
    Supervised craft for Director Board — same agents as CLI, stops before export.

    Why: UI and ``run_story_job`` must share screenplay→breakdown→supervise path.
    """
    if not _LANGGRAPH_AVAILABLE:
        return _run_brief_craft_fallback(
            brief,
            job_dir,
            extras=extras,
            style_profile=style_profile,
            max_revision_passes=max_revision_passes,
            on_phase=on_phase,
        )
    job_path = Path(job_dir)
    job_path.mkdir(parents=True, exist_ok=True)
    ex = dict(extras or {})
    init: StudioJobState = {
        "mode": "brief",
        "brief": brief,
        "job_dir": str(job_path.resolve()),
        "extras": ex,
        "style_profile": dict(style_profile or {}),
        "max_revision_passes": max_revision_passes,
        "revision_passes": 0,
        "screenplay_approved": bool(ex.get("skip_screenplay_gate")),
        "logs": [],
        "ok": False,
        "awaiting_approve": False,
        "awaiting_screenplay": False,
    }
    if on_phase is not None:
        on_phase("craft:شروع — سناریو → breakdown → storyboard")
    cfg = _graph_config(job_path, thread_id=thread_id)
    final = _finalize_state(_get_compiled("brief_craft").invoke(init, config=cfg))
    _save_checkpoint(job_path, "brief_craft_graph.json", final)
    if on_phase is not None:
        for line in final.get("logs") or []:
            on_phase(line)
        sup = final.get("supervisor") or {}
        on_phase(
            f"craft:supervisor passed={sup.get('passed')} "
            f"revision={final.get('revision_passes')}"
        )
    return final


def park_craft_for_screenplay(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    thread_id: str | None = None,
    on_phase: Any | None = None,
) -> StudioJobState:
    """Start craft graph and pause at screenplay approval (before storyboard)."""
    extras = dict(extras or {})
    extras.pop("skip_screenplay_gate", None)
    return run_brief_craft_graph(
        brief,
        job_dir,
        extras=extras,
        style_profile=style_profile,
        max_revision_passes=int(extras.get("max_revision_passes") or 2),
        thread_id=thread_id,
        on_phase=on_phase,
    )


def resume_craft_after_screenplay(
    job_dir: Path | str,
    *,
    approved: bool = True,
    screenplay: dict[str, Any] | None = None,
    thread_id: str | None = None,
    on_phase: Any | None = None,
) -> StudioJobState:
    """Continue craft graph after human screenplay approval."""
    if not _LANGGRAPH_AVAILABLE:
        return _resume_craft_fallback(
            job_dir, approved=approved, screenplay=screenplay, on_phase=on_phase
        )
    job_path = Path(job_dir)
    payload: dict[str, Any] = {"screenplay_approved": approved}
    if screenplay:
        payload["screenplay"] = screenplay
    cfg = _graph_config(job_path, thread_id=thread_id)
    if on_phase is not None:
        on_phase("craft:ادامه بعد از تأیید سناریو")
    final = _finalize_state(
        _get_compiled("brief_craft").invoke(Command(resume=payload), config=cfg)  # type: ignore[arg-type]
    )
    _save_checkpoint(job_path, "brief_craft_graph.json", final)
    if on_phase is not None:
        for line in final.get("logs") or []:
            on_phase(line)
    return final


def run_brief_studio_graph(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    targets: list[str] | None = None,
    max_revision_passes: int = 2,
    thread_id: str | None = None,
) -> StudioJobState:
    """Run full brief pipeline: craft → supervise → revise* → export → gate → render (opt)."""
    if not _LANGGRAPH_AVAILABLE:
        return _run_brief_fallback(
            brief,
            job_dir,
            extras=extras,
            style_profile=style_profile,
            targets=targets,
            max_revision_passes=max_revision_passes,
        )
    job_path = Path(job_dir)
    job_path.mkdir(parents=True, exist_ok=True)
    ex = dict(extras or {})
    ex.setdefault("skip_screenplay_gate", True)
    do_render = bool(ex.get("render"))
    init: StudioJobState = {
        "mode": "brief",
        "brief": brief,
        "job_dir": str(job_path.resolve()),
        "extras": ex,
        "style_profile": dict(style_profile or {}),
        "targets": list(targets or []),
        "max_revision_passes": max_revision_passes,
        "revision_passes": 0,
        "logs": [],
        "ok": False,
        "awaiting_approve": False,
        "render_requested": do_render,
        "render_mode": "direct_render" if do_render else "",
    }
    cfg = _graph_config(job_path, thread_id=thread_id)
    final = _finalize_state(_get_compiled("brief").invoke(init, config=cfg))
    _save_checkpoint(job_path, "brief_graph.json", final)
    return final


def park_spec_export_graph(
    spec_dict: dict[str, Any],
    job_dir: Path | str,
    *,
    targets: list[str] | None = None,
    extras: dict[str, Any] | None = None,
    thread_id: str | None = None,
) -> StudioJobState:
    """Start Director export graph and pause at await_approve (human-in-the-loop)."""
    if not _LANGGRAPH_AVAILABLE:
        out = _run_spec_fallback(
            spec_dict, job_dir, approved=False, targets=targets, extras=extras
        )
        out["awaiting_approve"] = True
        out["phase"] = "await_approve"
        return out
    job_path = Path(job_dir)
    ex = dict(extras or {})
    do_render = bool(ex.get("render"))
    init: StudioJobState = {
        "mode": "spec",
        "job_dir": str(job_path.resolve()),
        "spec": spec_dict,
        "approved": False,
        "targets": list(targets or []),
        "extras": ex,
        "logs": [],
        "ok": False,
        "awaiting_approve": False,
        "render_requested": do_render,
        "render_mode": "direct_render" if do_render else "",
    }
    cfg = _graph_config(job_path, thread_id=thread_id)
    final = _finalize_state(_get_compiled("spec").invoke(init, config=cfg))
    _save_checkpoint(job_path, "export_graph.json", final)
    return final


def resume_spec_export_graph(
    job_dir: Path | str,
    *,
    approved: bool = True,
    spec_dict: dict[str, Any] | None = None,
    targets: list[str] | None = None,
    thread_id: str | None = None,
) -> StudioJobState:
    """Resume paused export graph after human Approve (or deny)."""
    if not _LANGGRAPH_AVAILABLE:
        if not spec_dict:
            return {
                "ok": False,
                "error": "spec required for fallback resume",
                "awaiting_approve": False,
            }
        return _run_spec_fallback(
            spec_dict, job_dir, approved=approved, targets=targets, extras=None
        )
    job_path = Path(job_dir)
    payload: dict[str, Any] = {"approved": approved}
    if spec_dict:
        payload["spec"] = spec_dict
    if targets:
        payload["targets"] = targets
    cfg = _graph_config(job_path, thread_id=thread_id)
    final = _finalize_state(
        _get_compiled("spec").invoke(Command(resume=payload), config=cfg)  # type: ignore[arg-type]
    )
    _save_checkpoint(job_path, "export_graph.json", final)
    return final


def run_spec_export_graph(
    spec_dict: dict[str, Any],
    job_dir: Path | str,
    *,
    approved: bool = True,
    targets: list[str] | None = None,
    extras: dict[str, Any] | None = None,
    thread_id: str | None = None,
) -> StudioJobState:
    """Director Board export: await_approve (optional skip) → export → gate → render (opt)."""
    if approved:
        if not _LANGGRAPH_AVAILABLE:
            return _run_spec_fallback(
                spec_dict, job_dir, approved=True, targets=targets, extras=extras
            )
        job_path = Path(job_dir)
        ex = dict(extras or {})
        do_render = bool(ex.get("render"))
        init: StudioJobState = {
            "mode": "spec",
            "job_dir": str(job_path.resolve()),
            "spec": spec_dict,
            "approved": True,
            "targets": list(targets or []),
            "extras": ex,
            "logs": [],
            "ok": False,
            "awaiting_approve": False,
            "render_requested": do_render,
            "render_mode": "direct_render" if do_render else "",
        }
        cfg = _graph_config(job_path, thread_id=thread_id)
        final = _finalize_state(_get_compiled("spec").invoke(init, config=cfg))
        _save_checkpoint(job_path, "export_graph.json", final)
        return final
    return park_spec_export_graph(
        spec_dict,
        job_dir,
        targets=targets,
        extras=extras,
        thread_id=thread_id,
    )


def _run_brief_craft_fallback(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None,
    style_profile: dict[str, Any] | None,
    max_revision_passes: int,
    on_phase: Any | None = None,
) -> StudioJobState:
    """Imperative craft fallback when langgraph is absent."""
    from agents.story_chain import run_story_agent_chain_with_supervision

    extras = dict(extras or {})
    extras["max_revision_passes"] = max_revision_passes
    if not extras.get("skip_screenplay_gate"):
        from agents.story_chain import run_draft_screenplay_phase

        if on_phase is not None:
            on_phase("craft:پیش‌نویس سناریو (fallback)")
        sp = run_draft_screenplay_phase(brief, job_dir, extras=extras)
        return {
            "mode": "brief",
            "brief": brief,
            "job_dir": str(Path(job_dir).resolve()),
            "screenplay": sp,
            "awaiting_screenplay": True,
            "phase": "await_screenplay",
            "logs": ["fallback=await_screenplay"],
            "ok": False,
        }
    if on_phase is not None:
        on_phase("craft:شروع — fallback imperative")
    sup = run_story_agent_chain_with_supervision(
        brief, job_dir, extras=extras, style_profile=style_profile
    )
    chain = sup.chain
    ok = bool(chain.storyboard.get("shots"))
    state: StudioJobState = {
        "mode": "brief",
        "brief": brief,
        "job_dir": str(Path(job_dir).resolve()),
        "chain": chain.to_dict(),
        "supervisor": sup.supervisor.to_dict(),
        "revision_passes": sup.revision_passes,
        "logs": ["fallback=imperative_craft"],
        "ok": ok,
        "phase": "craft_complete",
        "error": "" if ok else "craft produced no shots",
        "awaiting_approve": False,
    }
    if on_phase is not None:
        for line in state.get("logs") or []:
            on_phase(line)
        on_phase(
            f"craft:supervisor passed={sup.supervisor.passed} "
            f"revision={sup.revision_passes}"
        )
    return state


def _run_brief_fallback(
    brief: str,
    job_dir: Path | str,
    *,
    extras: dict[str, Any] | None,
    style_profile: dict[str, Any] | None,
    targets: list[str] | None,
    max_revision_passes: int,
) -> StudioJobState:
    """Imperative fallback when langgraph is absent."""
    from agents.story_chain import run_story_agent_chain_with_supervision

    extras = dict(extras or {})
    extras["max_revision_passes"] = max_revision_passes
    sup = run_story_agent_chain_with_supervision(
        brief, job_dir, extras=extras, style_profile=style_profile
    )
    chain = sup.chain
    render_requested = bool(extras.get("render"))
    render_mode = "direct_render" if render_requested else "code_only"
    state: StudioJobState = {
        "mode": "brief",
        "brief": brief,
        "job_dir": str(Path(job_dir).resolve()),
        "chain": chain.to_dict(),
        "supervisor": sup.supervisor.to_dict(),
        "revision_passes": sup.revision_passes,
        "logs": ["fallback=imperative"],
        "awaiting_approve": False,
        "render_requested": render_requested,
        "render_mode": render_mode,
    }
    state.update(
        _node_export(
            {
                **state,
                "extras": extras,
                "style_profile": style_profile or {},
                "targets": targets or [],
            }
        )
    )
    state.update(_node_gate(state))
    if render_requested and state.get("ok"):
        state.update(_node_render(state))
    return state


def _run_spec_fallback(
    spec_dict: dict[str, Any],
    job_dir: Path | str,
    *,
    approved: bool,
    targets: list[str] | None,
    extras: dict[str, Any] | None,
) -> StudioJobState:
    ex = dict(extras or {})
    render_requested = bool(ex.get("render"))
    render_mode = "direct_render" if render_requested else "code_only"
    state: StudioJobState = {
        "mode": "spec",
        "job_dir": str(Path(job_dir).resolve()),
        "spec": spec_dict,
        "approved": approved,
        "targets": list(targets or []),
        "extras": ex,
        "logs": ["fallback=imperative"],
        "awaiting_approve": False,
        "render_requested": render_requested,
        "render_mode": render_mode,
    }
    if not approved:
        state.update(_node_blocked(state))
        return state
    state.update(_node_export(state))
    state.update(_node_gate(state))
    if render_requested and state.get("ok"):
        state.update(_node_render(state))
    return state


def _resume_craft_fallback(
    job_dir: Path | str,
    *,
    approved: bool,
    screenplay: dict[str, Any] | None,
    on_phase: Any | None = None,
) -> StudioJobState:
    """Resume craft without LangGraph after screenplay approval."""
    if not approved:
        return {
            "ok": False,
            "error": "Screenplay not approved",
            "phase": "screenplay_blocked",
            "awaiting_screenplay": False,
            "logs": ["fallback=screenplay_denied"],
        }
    root = Path(job_dir)
    pending_path = root / "design" / "screenplay_pending.json"
    pending = (
        json.loads(pending_path.read_text(encoding="utf-8"))
        if pending_path.is_file()
        else {}
    )
    brief = str(pending.get("brief") or "")
    from agents.story_chain import run_craft_from_screenplay

    extras = {
        "runtime_seconds": pending.get("runtime_seconds"),
        "use_llm": pending.get("use_llm"),
        "emotion": pending.get("emotion"),
        "character_path": pending.get("character_path"),
        "quality": pending.get("quality"),
        "style_id": pending.get("style_id"),
        "quality_gate_strict": False,
    }
    draft_path = root / "design" / "screenplay_draft.json"
    sp = screenplay or (
        json.loads(draft_path.read_text(encoding="utf-8")) if draft_path.is_file() else {}
    )
    if on_phase is not None:
        on_phase("craft:visual fallback")
    chain = run_craft_from_screenplay(brief, root, sp, extras=extras)
    ok = bool(chain.storyboard.get("shots"))
    return {
        "mode": "brief",
        "brief": brief,
        "job_dir": str(root.resolve()),
        "screenplay": sp,
        "screenplay_approved": True,
        "chain": chain.to_dict(),
        "ok": ok,
        "phase": "craft_complete",
        "logs": ["fallback=resume_craft"],
        "awaiting_screenplay": False,
    }
