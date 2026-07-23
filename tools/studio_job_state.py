"""
Studio job state for LangGraph orchestration.

Why: one typed state carries brief→craft→supervise→export→gate without ad-hoc dicts.
"""

from __future__ import annotations

from typing import Any, TypedDict


class StudioJobState(TypedDict, total=False):
    """Shared graph state for brief jobs and approved-spec export."""

    mode: str  # brief | spec
    brief: str
    job_dir: str
    extras: dict[str, Any]
    style_profile: dict[str, Any]
    targets: list[str]
    max_revision_passes: int
    revision_passes: int
    chain: dict[str, Any]
    screenplay: dict[str, Any]
    screenplay_approved: bool
    supervisor: dict[str, Any]
    spec: dict[str, Any]
    approved: bool
    bundle: dict[str, Any]
    gate: dict[str, Any]
    artifacts: dict[str, Any]
    ok: bool
    error: str
    phase: str
    logs: list[str]
    awaiting_approve: bool
    awaiting_screenplay: bool
    # Phase E — render
    render_requested: bool
    render_mode: str  # code_only | direct_render
    render_result: dict[str, Any]


def interrupt_kinds(state: dict[str, Any]) -> list[str]:
    """Extract human-gate kinds from LangGraph ``__interrupt__`` payloads."""
    kinds: list[str] = []
    for item in state.get("__interrupt__") or []:
        val = getattr(item, "value", item)
        if isinstance(val, dict):
            kind = val.get("kind")
            if kind:
                kinds.append(str(kind))
    return kinds


def has_interrupt(state: dict[str, Any]) -> bool:
    """True when graph paused at human-in-the-loop gate."""
    return bool(state.get("__interrupt__")) or bool(state.get("awaiting_approve"))


def has_screenplay_interrupt(state: dict[str, Any]) -> bool:
    """True when graph paused for screenplay approval before storyboard."""
    if state.get("awaiting_screenplay"):
        return True
    return "await_screenplay" in interrupt_kinds(state)


def has_approve_interrupt(state: dict[str, Any]) -> bool:
    """True when graph paused for Director export approval."""
    if state.get("awaiting_approve"):
        return True
    return "await_approve" in interrupt_kinds(state)


def append_log(state: StudioJobState, line: str) -> list[str]:
    """Return logs list with one new entry."""
    logs = list(state.get("logs") or [])
    logs.append(line)
    return logs
