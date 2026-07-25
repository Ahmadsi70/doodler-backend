"""
Director Board — design preview → revise patch → approve → render gate.

Why: the Director Board gives a human director a code-first surface on top of
the supervised craft graph. It wraps ``StudioSpec`` with status tracking, prompt
revision, approval gating, and export bundle creation.

Flow:
  1. ``design_from_brief()`` — runs craft graph, produces a ``DirectorBoard`` in
     ``preview`` status.
  2. ``revise_design()`` / ``apply_revise_prompt()`` — patch shots from text.
  3. ``approve_design()`` — flips status to ``approved``.
  4. ``render_approved_design()`` — export bundle + optional render (gated on approval).
  5. ``export_design_bundle()`` — copy spec + preview + board JSON for download.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore


@dataclass
class DirectorBoard:
    """Stateful wrapper around a ``StudioSpec`` with approval and revision tracking."""

    spec: StudioSpec
    status: str = "designed"
    approved: bool = False
    brief: str = ""
    revision_count: int = 0
    job_dir: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["spec"] = self.spec.to_public_dict()
        return d


# ── Design from brief ────────────────────────────────────────────────────


def design_from_brief(
    brief: str,
    *,
    job_dir: Path | str,
    quality: str = "light",
    runtime_seconds: float = 24,
    use_llm: bool = False,
    on_phase: Callable[[str], None] | None = None,
) -> DirectorBoard:
    """
    Run the supervised craft graph and produce a design preview ``DirectorBoard``.

    The board is in ``preview`` status — not yet approved for render.
    """
    from tools.studio_graph import run_brief_craft_graph

    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)

    extras: dict[str, Any] = {
        "quality": quality,
        "runtime_seconds": runtime_seconds,
        "use_llm": use_llm,
        "skip_screenplay_gate": True,
    }

    if on_phase is not None:
        on_phase("design:شروع craft graph")

    state = run_brief_craft_graph(
        brief,
        job,
        extras=extras,
        max_revision_passes=2,
        on_phase=on_phase,
    )

    chain = state.get("chain") or {}
    storyboard = chain.get("storyboard") or {}
    shots_data = storyboard.get("shots") or []

    # Build StudioSpec from chain shots
    spec_shots: list[ShotControl] = []
    for sh in shots_data:
        pose = str(sh.get("pose") or "idle")
        if pose not in {"idle", "walk", "react", "run"}:
            pose = "idle"
        beat = str(sh.get("story_beat") or "decision")
        if beat not in {"entrance", "reveal", "reaction", "conflict",
                         "decision", "quiet_hold", "exit"}:
            beat = "decision"
        camera = str(sh.get("camera") or "static")
        if camera not in {"static", "motivated_push", "pan_follow", "reveal_drift"}:
            camera = "static"
        spec_shots.append(ShotControl(
            title=str(sh.get("title") or ""),
            action=str(sh.get("action") or "Action."),
            duration_sec=float(sh.get("duration_sec") or 3.0),
            camera=camera,
            pose=pose,
            story_beat=beat,
            expression=str(sh.get("expression") or "neutral"),
        ))

    if not spec_shots:
        spec_shots = [ShotControl(action="Scene plays out.", duration_sec=3.0)]

    spec = StudioSpec(
        title=str(brief[:48] or "Story"),
        quality=quality,
        mode="direct",
        runtime_seconds=float(runtime_seconds),
        use_llm=use_llm,
        shots=spec_shots,
    )

    board = DirectorBoard(
        spec=spec,
        status="preview",
        approved=False,
        brief=brief,
        job_dir=str(job.resolve()),
    )

    # Persist artifacts
    _save_spec(spec, job)
    _save_board(board, job)
    _save_design_preview(board, job)
    _save_craft_meta(state, job)

    return board


# ── Park / finish screenplay ─────────────────────────────────────────────


def park_design_for_screenplay(
    brief: str,
    *,
    job_dir: Path | str,
    runtime_seconds: float = 24,
    use_llm: bool = False,
    quality: str = "light",
) -> DirectorBoard:
    """
    Start craft and pause at screenplay approval (before storyboard).

    Saves ``design/screenplay_draft.json`` for human editing.
    """
    from tools.studio_graph import park_craft_for_screenplay

    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)

    state = park_craft_for_screenplay(
        brief,
        job,
        extras={
            "quality": quality,
            "runtime_seconds": runtime_seconds,
            "use_llm": use_llm,
        },
    )

    # Save screenplay draft for editing
    screenplay = state.get("screenplay") or {}
    draft_dir = job / "design"
    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / "screenplay_draft.json").write_text(
        json.dumps(screenplay, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Save pending info for resume
    (draft_dir / "screenplay_pending.json").write_text(
        json.dumps({
            "brief": brief,
            "runtime_seconds": runtime_seconds,
            "use_llm": use_llm,
            "quality": quality,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    spec = StudioSpec(
        title=str(brief[:48] or "Story"),
        quality=quality,
        mode="direct",
        runtime_seconds=float(runtime_seconds),
        use_llm=use_llm,
        shots=[ShotControl(action="Awaiting screenplay.", duration_sec=3.0)],
    )

    board = DirectorBoard(
        spec=spec,
        status="awaiting_screenplay",
        approved=False,
        brief=brief,
        job_dir=str(job.resolve()),
    )
    _save_board(board, job)
    return board


def finish_design_after_screenplay(
    brief: str,
    *,
    job_dir: Path | str,
    screenplay_md: str,
    runtime_seconds: float = 24,
    use_llm: bool = False,
    quality: str = "light",
) -> DirectorBoard:
    """
    Resume craft after human screenplay approval with an edited screenplay.

    Saves the edited screenplay to ``agents/draft_screenplay.json`` and
    produces a ``DirectorBoard`` in ``preview`` status.
    """
    from tools.studio_graph import resume_craft_after_screenplay

    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)

    # Load existing draft and update screenplay_md
    draft_path = job / "design" / "screenplay_draft.json"
    draft: dict[str, Any] = {}
    if draft_path.is_file():
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["screenplay_md"] = screenplay_md

    # Save updated screenplay to agents dir (expected by resume)
    agents_dir = job / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "draft_screenplay.json").write_text(
        json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Also update the design draft
    draft_path.write_text(
        json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    state = resume_craft_after_screenplay(
        job,
        approved=True,
        screenplay=draft,
    )

    chain = state.get("chain") or {}
    storyboard = chain.get("storyboard") or {}
    shots_data = storyboard.get("shots") or []

    spec_shots = _shots_from_storyboard(shots_data)
    if not spec_shots:
        spec_shots = [ShotControl(action="Scene plays out.", duration_sec=3.0)]

    spec = StudioSpec(
        title=str(brief[:48] or "Story"),
        quality=quality,
        mode="direct",
        runtime_seconds=float(runtime_seconds),
        use_llm=use_llm,
        shots=spec_shots,
    )

    board = DirectorBoard(
        spec=spec,
        status="preview",
        approved=False,
        brief=brief,
        job_dir=str(job.resolve()),
    )
    _save_spec(spec, job)
    _save_board(board, job)
    _save_design_preview(board, job)
    _save_craft_meta(state, job)
    return board


# ── Revise ───────────────────────────────────────────────────────────────


def apply_revise_prompt(
    spec: StudioSpec,
    text: str,
    *,
    shot_indices: list[int] | None = None,
) -> tuple[StudioSpec, list[str]]:
    """
    Parse a multi-line revision prompt and apply changes to *shot_indices*.

    Supported line commands:
      ``dialogue: <text>``
      ``beat: <story_beat>``
      ``camera: <camera_name>``
      ``pose: <pose_name>``
      ``action: <text>``
      ``title: <text>``

    Returns a new ``StudioSpec`` and a list of human-readable notes.
    """
    notes: list[str] = []
    new_shots = [s.model_copy() for s in spec.shots]
    targets = shot_indices if shot_indices is not None else list(range(len(new_shots)))

    current_field: str | None = None

    for line in (text or "").strip().splitlines():
        line = line.strip()
        if not line:
            current_field = None
            continue

        # Check for "field: value" pattern
        match = re.match(r"^(\w+)\s*:\s*(.+)$", line)
        if match:
            field_name = match.group(1).lower()
            field_value = match.group(2).strip()

            field_map = {
                "dialogue": "dialogue",
                "beat": "story_beat",
                "camera": "camera",
                "pose": "pose",
                "action": "action",
                "title": "title",
                "expression": "expression",
            }

            if field_name in field_map:
                mapped = field_map[field_name]
                for idx in targets:
                    if 0 <= idx < len(new_shots):
                        # Validate enum fields
                        if mapped == "pose" and field_value not in {"idle", "walk", "react", "run"}:
                            notes.append(f"skip: invalid pose '{field_value}'")
                            continue
                        if mapped == "camera" and field_value not in {"static", "motivated_push", "pan_follow", "reveal_drift"}:
                            notes.append(f"skip: invalid camera '{field_value}'")
                            continue
                        if mapped == "story_beat" and field_value not in {"entrance", "reveal", "reaction", "conflict", "decision", "quiet_hold", "exit"}:
                            notes.append(f"skip: invalid beat '{field_value}'")
                            continue
                        setattr(new_shots[idx], mapped, field_value)
                        notes.append(f"set shot[{idx}].{mapped} = {field_value[:50]}")
                current_field = mapped
            else:
                current_field = None
        elif current_field:
            # Continuation of previous multi-line field
            for idx in targets:
                if 0 <= idx < len(new_shots):
                    old = getattr(new_shots[idx], current_field, "")
                    setattr(new_shots[idx], current_field, f"{old}\n{line}")

    new_spec = spec.model_copy(update={"shots": new_shots})
    return new_spec, notes


def revise_design(
    board: DirectorBoard,
    *,
    revise_prompt: str,
    shot_indices: list[int],
    locked_fields: dict[int, set[str]] | None = None,
    job_dir: Path | str | None = None,
) -> DirectorBoard:
    """
    Apply a natural-language revision to selected shots, respecting locked fields.

    The *revise_prompt* is parsed for camera/pose/action keywords. Fields in
    ``locked_fields[shot_index]`` are never changed.

    Saves revision history to ``design/revise_history.json``.
    """
    locked = locked_fields or {}
    spec = board.spec

    # Parse keywords from prompt
    prompt_lower = (revise_prompt or "").lower()

    # Detect camera and pose from prompt
    camera_override: str | None = None
    if "static" in prompt_lower:
        camera_override = "static"
    elif "push" in prompt_lower or "motivated" in prompt_lower:
        camera_override = "motivated_push"
    elif "pan" in prompt_lower or "follow" in prompt_lower:
        camera_override = "pan_follow"
    elif "reveal" in prompt_lower or "drift" in prompt_lower:
        camera_override = "reveal_drift"

    pose_override: str | None = None
    if "idle" in prompt_lower:
        pose_override = "idle"
    elif "walk" in prompt_lower:
        pose_override = "walk"
    elif "react" in prompt_lower:
        pose_override = "react"
    elif "run" in prompt_lower:
        pose_override = "run"

    new_shots = [s.model_copy() for s in spec.shots]

    for idx in shot_indices:
        if idx < 0 or idx >= len(new_shots):
            continue
        locked_for_shot = locked.get(idx, set())

        if camera_override and "camera" not in locked_for_shot:
            new_shots[idx].camera = camera_override
        if pose_override and "pose" not in locked_for_shot:
            new_shots[idx].pose = pose_override

    # Also apply structured prompt commands (dialogue, beat, etc.)
    new_spec, notes = apply_revise_prompt(
        spec.model_copy(update={"shots": new_shots}),
        revise_prompt,
        shot_indices=shot_indices,
    )

    # Save revision history
    job = Path(job_dir or board.job_dir or ".")
    history_path = job / "design" / "revise_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    history: dict[str, Any] = {"revisions": []}
    if history_path.is_file():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    history["revisions"].append({
        "prompt": revise_prompt,
        "shot_indices": shot_indices,
        "locked_fields": {k: sorted(v) for k, v in locked.items()},
        "notes": notes,
    })
    history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return DirectorBoard(
        spec=new_spec,
        status=board.status,
        approved=board.approved,
        brief=board.brief,
        revision_count=board.revision_count + 1,
        job_dir=str(job.resolve()),
        notes=board.notes + notes,
    )


# ── Approve & Render ─────────────────────────────────────────────────────


def approve_design(board: DirectorBoard, *, job_dir: Path | str | None = None) -> DirectorBoard:
    """Flip board to ``approved`` status and persist."""
    job = Path(job_dir or board.job_dir or ".")
    new_board = DirectorBoard(
        spec=board.spec,
        status="approved",
        approved=True,
        brief=board.brief,
        revision_count=board.revision_count,
        job_dir=str(job.resolve()),
        notes=board.notes,
    )
    _save_board(new_board, job)
    return new_board


def render_approved_design(
    board: DirectorBoard,
    *,
    job_dir: Path | str | None = None,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    """
    Export bundle (and optionally render) from an approved design.

    Returns ``{"ok": bool, "control_plane": "studio_spec", ...}``.
    Blocked when board is not approved.
    """
    if not board.approved:
        return {"ok": False, "error": "Design not approved", "control_plane": "studio_spec"}

    from tools.studio_api import export_from_spec

    job = Path(job_dir or board.job_dir or ".")
    spec = board.spec.model_copy(update={"mode": "direct"})

    result = export_from_spec(
        spec,
        workspace=job,
        targets=targets,
        render=bool(board.spec.use_llm),
    )
    return {
        "ok": bool(result.get("ok")),
        "control_plane": "studio_spec",
        "artifacts": result.get("artifacts") or {},
        "error": str(result.get("error") or ""),
    }


# ── Export bundle ────────────────────────────────────────────────────────


def export_design_bundle(board: DirectorBoard, dest: Path | str) -> Path:
    """Copy studio_spec.json, design_preview.md, director_board.json to *dest*."""
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    job = Path(board.job_dir or ".")

    # studio_spec.json
    spec_src = job / "studio_spec.json"
    if spec_src.is_file():
        (out / "studio_spec.json").write_text(spec_src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Generate from spec
        (out / "studio_spec.json").write_text(
            json.dumps(board.spec.to_public_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # design_preview.md
    preview_src = job / "design" / "design_preview.md"
    if preview_src.is_file():
        (out / "design_preview.md").write_text(preview_src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        (out / "design_preview.md").write_text(_design_preview_md(board), encoding="utf-8")

    # director_board.json
    (out / "director_board.json").write_text(
        json.dumps(board.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return out


# ── Update shot manual ───────────────────────────────────────────────────


def update_shot_manual(
    board: DirectorBoard,
    shot_index: int,
    updates: dict[str, Any],
    *,
    job_dir: Path | str | None = None,
) -> DirectorBoard:
    """Apply manual field updates to a single shot and return a new board."""
    new_shots = [s.model_copy() for s in board.spec.shots]
    if 0 <= shot_index < len(new_shots):
        shot = new_shots[shot_index]
        for key, val in updates.items():
            if hasattr(shot, key) and val is not None:
                setattr(shot, key, val)

    job = Path(job_dir or board.job_dir or ".")
    new_spec = board.spec.model_copy(update={"shots": new_shots})
    new_board = DirectorBoard(
        spec=new_spec,
        status=board.status,
        approved=board.approved,
        brief=board.brief,
        revision_count=board.revision_count,
        job_dir=str(job.resolve()),
        notes=board.notes + [f"manual: shot[{shot_index}] updated"],
    )
    _save_spec(new_spec, job)
    _save_board(new_board, job)
    return new_board


# ── Act table rows ───────────────────────────────────────────────────────


def act_table_rows(spec: StudioSpec, plan: Any) -> list[dict[str, Any]]:
    """
    Render an ``ActPlan`` as table rows with act metadata and shot indices.

    Each row has: ``act_id``, ``title``, ``shots``, ``duration_sec``.
    """
    rows: list[dict[str, Any]] = []
    for act in plan.acts:
        rows.append({
            "act_id": act.id,
            "title": act.title,
            "shots": f"{act.shot_start}–{act.shot_end - 1}",
            "shot_start": act.shot_start,
            "shot_end": act.shot_end,
            "duration_sec": round(act.duration_sec, 1),
            "summary": act.summary,
        })
    return rows


# ── Internal helpers ─────────────────────────────────────────────────────


def _shots_from_storyboard(shots_data: list[dict[str, Any]]) -> list[ShotControl]:
    """Convert raw storyboard shot dicts to ``ShotControl`` list."""
    spec_shots: list[ShotControl] = []
    for sh in shots_data:
        pose = str(sh.get("pose") or "idle")
        if pose not in {"idle", "walk", "react", "run"}:
            pose = "idle"
        beat = str(sh.get("story_beat") or "decision")
        if beat not in {"entrance", "reveal", "reaction", "conflict",
                         "decision", "quiet_hold", "exit"}:
            beat = "decision"
        camera = str(sh.get("camera") or "static")
        if camera not in {"static", "motivated_push", "pan_follow", "reveal_drift"}:
            camera = "static"
        spec_shots.append(ShotControl(
            title=str(sh.get("title") or ""),
            action=str(sh.get("action") or "Action."),
            duration_sec=float(sh.get("duration_sec") or 3.0),
            camera=camera,
            pose=pose,
            story_beat=beat,
            expression=str(sh.get("expression") or "neutral"),
        ))
    return spec_shots


def _save_spec(spec: StudioSpec, job: Path) -> None:
    """Save studio_spec.json to job root."""
    (job / "studio_spec.json").write_text(
        json.dumps(spec.to_public_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _save_board(board: DirectorBoard, job: Path) -> None:
    """Save director_board.json to design dir."""
    design_dir = job / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "director_board.json").write_text(
        json.dumps(board.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _save_design_preview(board: DirectorBoard, job: Path) -> None:
    """Write a human-readable design preview markdown."""
    design_dir = job / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "design_preview.md").write_text(
        _design_preview_md(board), encoding="utf-8"
    )


def _save_craft_meta(state: dict[str, Any], job: Path) -> None:
    """Save craft metadata (graph type, supervisor summary)."""
    design_dir = job / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    sup = state.get("supervisor") or {}
    meta = {
        "graph": "brief_craft",
        "supervisor": {
            "passed": sup.get("passed"),
            "score": sup.get("score"),
            "revision_target": sup.get("revision_target"),
        },
        "revision_passes": state.get("revision_passes", 0),
        "phase": state.get("phase"),
    }
    (design_dir / "craft_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _design_preview_md(board: DirectorBoard) -> str:
    """Generate a markdown preview of the design."""
    lines = [
        f"# {board.spec.title}",
        "",
        f"**Status:** {board.status}",
        f"**Approved:** {'yes' if board.approved else 'no'}",
        f"**Quality:** {board.spec.quality}",
        f"**Runtime:** {board.spec.runtime_seconds}s",
        f"**Revisions:** {board.revision_count}",
        "",
        "## Shots",
        "",
    ]
    for i, shot in enumerate(board.spec.shots):
        lines.append(f"### Shot {i}: {shot.title or '(untitled)'}")
        lines.append(f"- **Action:** {shot.action}")
        lines.append(f"- **Camera:** {shot.camera} | **Pose:** {shot.pose}")
        lines.append(f"- **Beat:** {shot.story_beat} | **Duration:** {shot.duration_sec}s")
        if shot.dialogue:
            lines.append(f"- **Dialogue:** {shot.dialogue}")
        lines.append("")
    return "\n".join(lines) + "\n"
