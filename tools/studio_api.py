"""
Code-first Story Studio API.

Why: authors control every shot from ``StudioSpec`` (Python/JSON). Agents become
optional; Remotion/Light consume the compiled artifacts directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from studio_spec import ShotControl, StudioSpec
except ImportError:
    from ..studio_spec import ShotControl, StudioSpec  # type: ignore

EventFn = Callable[[str, Any], None]


@dataclass
class CompiledStudio:
    """Agent-shaped artifacts produced from StudioSpec (control plane)."""

    storyboard: dict[str, Any]
    cinematography: dict[str, Any]
    timing: dict[str, Any]
    continuity: dict[str, Any]
    brief: str
    control_plane: str = "studio_spec"
    notes: list[str] = field(default_factory=list)


def load_studio_spec(path: Path | str) -> StudioSpec:
    """Load StudioSpec from JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return StudioSpec.model_validate(data)


def save_studio_spec(spec: StudioSpec, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(spec.to_public_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def write_studio_spec_example(path: Path | str) -> Path:
    """Write a starter spec authors can edit."""
    spec = StudioSpec(
        title="Example Code Studio",
        quality="pro",
        mode="direct",
        runtime_seconds=24,
        use_agents=False,
        character_path=None,
        shots=[
            ShotControl(
                title="Enter",
                action="The hero enters a quiet archive.",
                duration_sec=3.0,
                lens="standard",
                camera="static",
                composition="L",
                pose="walk",
                expression="neutral",
                story_beat="entrance",
                anticipation_frames=6,
                hold_frames=12,
            ),
            ShotControl(
                title="Shock",
                action="Then they react in shock because the letter burns.",
                duration_sec=4.0,
                lens="action",
                camera="motivated_push",
                composition="C",
                pose="react",
                expression="shock",
                story_beat="reaction",
                anticipation_frames=8,
                hold_frames=16,
            ),
            ShotControl(
                title="Exit",
                action="They leave into the rain.",
                duration_sec=3.0,
                lens="beauty",
                camera="static",
                composition="R",
                pose="walk",
                expression="worry",
                story_beat="exit",
                anticipation_frames=5,
                hold_frames=12,
            ),
        ],
    )
    return save_studio_spec(spec, path)


def compile_studio_spec(spec: StudioSpec) -> CompiledStudio:
    """
    Compile StudioSpec → storyboard / cine / timing / continuity dicts.

    Direct mode preserves author numbers; still tags Williams story beats for
    Remotion craftHints / envProfile.
    """
    fps = 24
    shots_sb: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    look_default = "right"
    for i, sh in enumerate(spec.shots):
        sid = i
        title = sh.title or f"Shot {i}"
        action = sh.action
        sec = float(sh.duration_sec)
        frames_n = max(12, int(round(sec * fps)))
        look = sh.look_space or (
            "right" if sh.composition == "L" else ("left" if sh.composition == "R" else "none")
        )
        shots_sb.append(
            {
                "shot_id": sid,
                "title": title,
                "action": action,
                "duration_sec": sec,
                "duration_frames": frames_n,
                "idea": action[:80],
                "verb": action.split()[0].lower() if action.split() else "holds",
                "narrative_question": f"What changes when: {action[:60]}",
                "focal_point": sh.pose,
                "composition_shape": sh.composition,
                "story_beat": sh.story_beat,
                "action_phases": [
                    {
                        "phase": "anticipation",
                        "frame_start": 0,
                        "frame_end": int(sh.anticipation_frames),
                    },
                    {
                        "phase": "action",
                        "frame_start": int(sh.anticipation_frames),
                        "frame_end": max(
                            int(sh.anticipation_frames) + 1,
                            frames_n - int(sh.hold_frames),
                        ),
                    },
                    {
                        "phase": "aftermath",
                        "frame_start": max(0, frames_n - int(sh.hold_frames)),
                        "frame_end": frames_n,
                    },
                ],
                "pose": sh.pose,
                "expression": sh.expression,
                "dialogue": sh.dialogue or "",
                "vo_path": sh.vo_path or "",
                "shot_size": sh.shot_size,
                "camera": sh.camera,
                "lens": sh.lens,
                "control": "studio_spec",
            }
        )
        frames.append(
            {
                "shot_id": sid,
                "lens": sh.lens,
                "composition": sh.composition,
                "camera": sh.camera,
                "shot_size": sh.shot_size,
                "lighting": sh.lighting,
                "look_space_direction": look if look != "" else "none",
                "counterchange": True,
                "camera_move": sh.camera,
                "story_beat": sh.story_beat,
                "williams_behavior_id": f"spec.{sh.story_beat}.{sh.pose}",
            }
        )
        timing_rows.append(
            {
                "shot_id": sid,
                "duration_sec": sec,
                "duration_frames": frames_n,
                "hold_frames": int(sh.hold_frames),
                "anticipation_frames": int(sh.anticipation_frames),
                "williams_story_beat": sh.story_beat,
                "williams_behavior_id": f"spec.{sh.story_beat}.{sh.pose}",
                "williams_rig": {"pose": sh.pose, "expression": sh.expression},
                "action_bias": "slow_in" if sh.pose == "react" else "even",
            }
        )
        direction = "L_to_R" if look != "left" else "R_to_L"
        checks.append(
            {
                "shot_id": sid,
                "screen_direction": direction,
                "eyeline": "consistent",
                "cause_before_effect": True,
                "lens": sh.lens,
                "camera": sh.camera,
                "look_space_direction": look,
            }
        )
        look_default = look

    line_side = "left" if look_default != "left" else "right"
    continuity = {
        "agent": "StudioSpec",
        "180_line_side": line_side,
        "eyeline_map": [{"character_id": "main", "looks": "right" if line_side == "left" else "left"}],
        "cut_notes": ["code_controlled"],
        "violations": [],
        "approved": True,
        "checks": checks,
        "system_prompt_loaded": False,
        "schema": "studio_spec#v1",
    }
    storyboard = {
        "agent": "StudioSpec",
        "shots": shots_sb,
        "system_prompt_loaded": False,
        "schema": "studio_spec#v1",
        "control_plane": "studio_spec",
    }
    cinematography = {
        "agent": "StudioSpec",
        "frames": frames,
        "system_prompt_loaded": False,
        "schema": "studio_spec#v1",
    }
    timing = {
        "agent": "StudioSpec",
        "fps": fps,
        "shots": timing_rows,
        "williams_craft_applied": True,
        "system_prompt_loaded": False,
        "schema": "studio_spec#v1",
    }
    return CompiledStudio(
        storyboard=storyboard,
        cinematography=cinematography,
        timing=timing,
        continuity=continuity,
        brief=spec.to_brief(),
        notes=[f"shots={len(spec.shots)}", f"mode={spec.mode}"],
    )


def export_from_spec(
    spec: StudioSpec,
    *,
    job_id: str | None = None,
    workspace: Path | str | None = None,
    on_event: EventFn | None = None,
    targets: list[str] | None = None,
    render: bool = False,
    render_mode: str = "direct_render",
) -> dict[str, Any]:
    """
    Compile StudioSpec and write animation export bundle.

    Pass ``render=True`` to trigger Phase E render after export.
    ``render_mode`` can be 'direct_render' (MP4) or 'code_only' (scripts).
    """
    from tools.animation_export import DEFAULT_TARGETS, export_animation_bundle
    from tools.job_workspace import job_workspace, new_job_id
    from tools.scene_ir_builder import build_scene_ir_from_chain

    def _emit(kind: str, payload: Any) -> None:
        if on_event:
            on_event(kind, payload)

    if workspace is not None:
        ws_path = Path(workspace)
        ws_path.mkdir(parents=True, exist_ok=True)
        jid = (job_id or "").strip() or ws_path.name or new_job_id()
        workspace = ws_path
    else:
        jid = (job_id or "").strip() or new_job_id()
        workspace = job_workspace(jid)
    save_studio_spec(spec, workspace / "studio_spec.json")
    compiled = compile_studio_spec(spec)
    _emit("phase", "StudioSpec compile…")
    _emit("log", f"control_plane=studio_spec mode={spec.mode}")

    storyboard = compiled.storyboard
    cinematography = compiled.cinematography
    timing = compiled.timing
    continuity = compiled.continuity
    character_rig: dict[str, Any] = {}
    act_plan = None
    ctx_pack = None

    try:
        from tools.act_planner import plan_acts
        from tools.context_pack import build_compressed_context
        from tools.continuity_graph import (
            build_continuity_graph,
            merge_graph_into_continuity,
        )

        act_plan = plan_acts(spec)
        graph = build_continuity_graph(
            storyboard=storyboard,
            cinematography=cinematography,
            continuity=continuity,
        )
        continuity = merge_graph_into_continuity(continuity, graph)
        gate = __import__(
            "tools.continuity_graph", fromlist=["continuity_gate"]
        ).continuity_gate(
            graph,
            strict=bool(
                __import__("os").environ.get("CONTINUITY_GATE_STRICT", "").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )
        continuity["gate"] = gate
        if gate.get("strict") and not gate.get("ok"):
            _emit("log", f"continuity_gate_block={gate.get('blocking')}")
            return {
                "ok": False,
                "exported": False,
                "rendered": False,
                "job_id": jid,
                "job_dir": str(workspace),
                "error": "Continuity gate blocked export (screen_direction_flip)",
                "artifacts": {},
                "notes": compiled.notes + ["continuity_gate=fail"],
            }
        ctx_pack = build_compressed_context(
            spec,
            act=act_plan.acts[0],
            bible=spec.title,
            prior_act_summaries=[],
        )
        (workspace / "act_plan.json").write_text(
            json.dumps(act_plan.to_public_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (workspace / "compressed_context.json").write_text(
            json.dumps(ctx_pack.model_dump(mode="json"), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        _emit("log", f"act_context_skip={exc!r}")

    if spec.mode == "agents" or spec.use_agents:
        _emit("phase", "Optional agents on synthesized brief…")
        try:
            from agents.story_chain import run_story_agent_chain

            chain = run_story_agent_chain(
                compiled.brief,
                workspace,
                extras={
                    "runtime_seconds": spec.runtime_seconds,
                    "use_llm": spec.use_llm,
                    "emotion": spec.emotion,
                    "character_path": spec.resolved_character(),
                    "quality_gate_strict": False,
                    "max_revision_passes": spec.max_revision_passes,
                },
            )
            if spec.mode != "direct":
                agent_shots = {
                    s.get("shot_id"): s for s in (chain.storyboard.get("shots") or [])
                }
                for row in storyboard["shots"]:
                    ag = agent_shots.get(row["shot_id"])
                    if ag and spec.use_llm:
                        row["action"] = str(ag.get("action") or row["action"])
            character_rig = chain.character_rig or {}
            _emit("log", "agents=merged_under_spec")
        except Exception as exc:  # noqa: BLE001
            _emit("log", f"agents_skip={exc!r}")

    agents_dir = workspace / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("storyboard.json", storyboard),
        ("cinematography.json", cinematography),
        ("animation_timing.json", timing),
        ("continuity.json", continuity),
    ):
        (agents_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if character_rig:
        (agents_dir / "character_rig.json").write_text(
            json.dumps(character_rig, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    ir = build_scene_ir_from_chain(
        compiled.brief,
        storyboard=storyboard,
        cinematography=cinematography,
        timing=timing,
        continuity=continuity,
        job_id=jid,
        job_out_dir=str(workspace),
        runtime_seconds=spec.runtime_seconds,
        compressed_context=ctx_pack,
        act_plan=act_plan.to_public_dict() if act_plan is not None else None,
    )
    (workspace / "scene_ir.json").write_text(
        ir.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    chosen = targets or list(DEFAULT_TARGETS)
    _emit("phase", "Export animation bundle…")
    export_dir = workspace / "export"
    bundle = export_animation_bundle(spec, export_dir, targets=chosen)  # type: ignore[arg-type]
    if not bundle.get("ok"):
        return {
            "ok": False,
            "exported": False,
            "rendered": False,
            "job_id": jid,
            "job_dir": str(workspace),
            "error": bundle.get("error") or "export bundle failed",
            "artifacts": {"export_root": bundle.get("export_root")},
            "notes": compiled.notes + ["export_only=fail"],
        }

    artifacts: dict[str, Any] = {
        "export_root": bundle["export_root"],
        "manifest": bundle["manifest"],
        "screenplay": bundle["screenplay"],
        "explanation": bundle["explanation"],
        "targets": bundle["targets"],
    }

    # Phase E — render
    render_result = None
    if render:
        _emit("phase", f"Phase E — render ({render_mode})…")
        try:
            from agents.render_agent import run_render_agent

            render_result = run_render_agent(
                export_dir,
                mode=render_mode,  # type: ignore[arg-type]
                quality=spec.quality or "light",
                title=spec.title or "Story",
            )
            artifacts["render"] = {
                "ok": render_result.ok,
                "backend": render_result.backend,
                "render_mp4": render_result.render_mp4,
                "code_dir": render_result.code_dir,
                "code_files": render_result.code_files,
                "run_command": render_result.run_command,
                "error": render_result.error,
                "logs": render_result.logs,
            }
            if render_result.render_mp4:
                artifacts["render_mp4"] = render_result.render_mp4
            if render_result.code_dir:
                artifacts["render_code_dir"] = render_result.code_dir
            _emit("log", f"render ok={render_result.ok} backend={render_result.backend}")
        except Exception as exc:  # noqa: BLE001
            _emit("log", f"render_skip={exc!r}")
            artifacts["render"] = {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "exported": True,
        "rendered": bool(render and render_result and render_result.ok),
        "job_id": jid,
        "job_dir": str(workspace),
        "control_plane": "studio_spec",
        "mode": spec.mode,
        "artifacts": artifacts,
        "compiled_only": False,
        "notes": compiled.notes + [f"export_only={'0' if render else '1'}"],
    }


def render_from_spec(
    spec: StudioSpec,
    *,
    job_id: str | None = None,
    workspace: Path | str | None = None,
    on_event: EventFn | None = None,
    render: bool = False,
) -> dict[str, Any]:
    """
    Export StudioSpec → bundle, optionally render to MP4.

    Pass ``render=True`` for Phase E direct render after export.
    """
    return export_from_spec(
        spec,
        job_id=job_id,
        workspace=workspace,
        on_event=on_event,
        render=render,
    )
