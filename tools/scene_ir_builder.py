"""
Build a real SceneIR from Story agent-chain artifacts.

Why: supervisor/pipeline used empty_scene_ir; craft and shots never entered the IR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scene_ir import (
        BoundingBox2D,
        CameraKeyframe,
        CameraPlan,
        CastMember,
        CausalOrigin,
        ContactMarker,
        FrameRange,
        MotivationMode,
        PhonemeMarker,
        PoseKeyframe,
        PerformanceTimeline,
        SceneIR,
        SceneNode,
        SceneSequence,
        ShotList,
        ShotSpec,
        StoryBeat,
        StoryBrief,
        StoryboardPlan,
        StoryboardSnapshot,
        Vec3,
        empty_compliance_pending,
    )
except ImportError:
    from ..scene_ir import (  # type: ignore
        BoundingBox2D,
        CameraKeyframe,
        CameraPlan,
        CastMember,
        CausalOrigin,
        ContactMarker,
        FrameRange,
        MotivationMode,
        PhonemeMarker,
        PoseKeyframe,
        PerformanceTimeline,
        SceneIR,
        SceneNode,
        SceneSequence,
        ShotList,
        ShotSpec,
        StoryBeat,
        StoryBrief,
        StoryboardPlan,
        StoryboardSnapshot,
        Vec3,
        empty_compliance_pending,
    )

_LENS_MAP = {
    "action": "wide",
    "standard": "normal",
    "beauty": "telephoto",
    "wide": "wide",
    "normal": "normal",
    "telephoto": "telephoto",
}


def _map_lens(raw: str | None) -> str:
    return _LENS_MAP.get(str(raw or "standard").lower(), "normal")


def build_scene_ir_from_chain(
    brief: str,
    *,
    storyboard: dict[str, Any],
    cinematography: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    job_id: str | None = None,
    job_out_dir: str | None = None,
    runtime_seconds: float | None = None,
    compressed_context: Any | None = None,
    act_plan: dict[str, Any] | None = None,
) -> SceneIR:
    """Populate StoryBrief / ShotList / CameraPlan / Storyboard from chain JSON."""
    shots = list(storyboard.get("shots") or [])
    timing_by = {s.get("shot_id"): s for s in (timing or {}).get("shots") or []}
    cine_by = {f.get("shot_id"): f for f in (cinematography or {}).get("frames") or []}
    cont = continuity or {}

    beats: list[StoryBeat] = []
    scene_nodes: list[SceneNode] = []
    shot_specs: list[ShotSpec] = []
    cam_keys: list[CameraKeyframe] = []
    poses: list[PoseKeyframe] = []
    snapshots: list[StoryboardSnapshot] = []

    cursor = 0
    for i, sh in enumerate(shots):
        sid = str(sh.get("shot_id") if sh.get("shot_id") is not None else i)
        action = str(sh.get("action") or sh.get("idea") or "")
        title = str(sh.get("title") or f"Shot {sid}")
        trow = timing_by.get(sh.get("shot_id")) or timing_by.get(sid) or {}
        crow = cine_by.get(sh.get("shot_id")) or cine_by.get(sid) or {}
        dur = int(
            trow.get("duration_frames")
            or max(12, round(float(sh.get("duration_sec") or 3.0) * 24))
        )
        fr = FrameRange(start_frame=cursor, end_frame=cursor + max(0, dur - 1))
        cursor += dur

        beats.append(
            StoryBeat(
                id=f"beat-{sid}",
                order=i,
                summary=action[:240] or title,
                emotional_intent=str(sh.get("story_beat") or ""),
            )
        )
        scene_nodes.append(
            SceneNode(
                id=f"scene-{sid}",
                order=i,
                title=title,
                summary=action[:240],
                stakes=min(1.0, 0.2 + 0.15 * i),
                motivation_mode=MotivationMode.REACTION
                if str(sh.get("story_beat") or "") == "reaction"
                else MotivationMode.ACTION,
                frame_range=fr,
            )
        )
        role: str = "root" if i == 0 else ("effect" if i == len(shots) - 1 else "cause")
        shot_specs.append(
            ShotSpec(
                id=f"shot-{sid}",
                scene_id=f"scene-{sid}",
                order=i,
                label=title,
                frame_range=fr,
                covers_subject_id="main",
                lens=_map_lens(crow.get("lens")),  # type: ignore[arg-type]
                causal_origin=CausalOrigin(
                    shot_id=f"shot-{sid}",
                    event_id=f"evt-{sid}",
                    kind="dramatic",
                    label=str(sh.get("verb") or "action"),
                ),
                causal_role=role,  # type: ignore[arg-type]
                notes=action[:200],
            )
        )
        cam_keys.append(
            CameraKeyframe(
                frame=fr.start_frame,
                position=Vec3(x=0.0, y=1.6, z=3.0 + 0.2 * i),
                look_at=Vec3(x=0.0, y=1.4, z=0.0),
                lens=_map_lens(crow.get("lens")),  # type: ignore[arg-type]
                fov_deg=55.0 if crow.get("lens") == "action" else 40.0,
            )
        )
        poses.append(
            PoseKeyframe(
                frame=fr.start_frame,
                subject_id="main",
                bbox=BoundingBox2D(min_x=0.15, min_y=0.12, max_x=0.48, max_y=0.92),
                phase=str(sh.get("story_beat") or "hold"),
                notes=str(sh.get("verb") or ""),
            )
        )
        snapshots.append(
            StoryboardSnapshot(
                frame=fr.start_frame,
                reason=title[:120] or f"shot-{sid}",
                subject_id="main",
                shot_id=f"shot-{sid}",
                notes=action[:160],
            )
        )

    line = str(cont.get("180_line_side") or "left")
    eyeline_a = "screenRight" if line == "left" else "screenLeft"
    eyeline_b = "screenLeft" if line == "left" else "screenRight"

    compliance = empty_compliance_pending()
    compliance = compliance.model_copy(
        update={
            "fps_is_24": True,
            "line_of_action_ok": bool(cont.get("approved", True)),
            "eyeline_continuity_ok": bool(cont.get("approved", True)),
            "all_shots_have_causal_origin": bool(shot_specs),
            "motivation_enforced": True,
            "notes": "filled_from_story_agent_chain",
        }
    )

    budget = float(runtime_seconds or cursor / 24.0 or 30.0)
    notes = ["scene_ir_from_chain=1"]
    if act_plan:
        notes.append("act_plan=1")
    if compressed_context is not None:
        notes.append("compressed_context=1")

    # Accept either FrozenModel or dict for compressed_context
    ctx = compressed_context
    if isinstance(compressed_context, dict):
        try:
            from scene_ir import CompressedContextPack as _CCP

            ctx = _CCP.model_validate(compressed_context)
        except Exception:  # noqa: BLE001
            ctx = None

    return SceneIR(
        user_prompt=brief,
        job_id=job_id,
        job_out_dir=job_out_dir,
        story_brief=StoryBrief(
            title="Story",
            user_prompt=brief,
            logline=(shots[0].get("action") if shots else brief)[:160]
            if shots
            else brief[:160],
            runtime_seconds_budget=max(1.0, budget),
            cast=[CastMember(id="main", name="Protagonist", role="protagonist")],
            beats=beats,
            notes="built_from_agent_chain"
            + (f" acts={len((act_plan or {}).get('acts') or [])}" if act_plan else ""),
        ),
        scene_sequence=SceneSequence(
            scenes=scene_nodes,
            macro_question="What changes for the protagonist?",
            hero_character_id="main",
        ),
        shot_list=ShotList(shots=shot_specs, notes="from AnimationTiming+Storyboard"),
        performance=PerformanceTimeline(
            fps=24,
            total_frames=max(0, cursor),
            keyframes=poses,
            notes="proxy poses from craft beats",
        ),
        camera_plan=CameraPlan(
            keyframes=cam_keys,
            tracking_subject_id="main",
            eyeline_a=eyeline_a,  # type: ignore[arg-type]
            eyeline_b=eyeline_b,  # type: ignore[arg-type]
            notes=f"180_line_side={line}",
        ),
        storyboard=StoryboardPlan(snapshots=snapshots, mode="animation"),
        compliance=compliance,
        compressed_context=ctx,
        notes=notes,
    )


def apply_frame_artifacts_to_scene_ir(
    ir: SceneIR,
    *,
    performance_chart: dict[str, Any] | None = None,
    contact_lock: dict[str, Any] | None = None,
    phoneme_sync: dict[str, Any] | None = None,
    compliance_frame: dict[str, Any] | None = None,
) -> SceneIR:
    """
    Merge P0–P3 frame agents into SceneIR.performance + compliance.

    Why: Remotion reads props; SceneIR is the audit bridge — must carry the same
    contacts/phonemes/dense keys for supervisor and export.
    """
    bbox = BoundingBox2D(min_x=0.15, min_y=0.12, max_x=0.48, max_y=0.92)
    keyframes: list[PoseKeyframe] = []
    cursor = 0
    total = 0
    for shot in (performance_chart or {}).get("shots") or []:
        dur = int(shot.get("duration_frames") or 0)
        total += dur
        for k in shot.get("keyframes") or []:
            local = int(k.get("frame") or 0)
            keyframes.append(
                PoseKeyframe(
                    frame=cursor + local,
                    subject_id="main",
                    bbox=bbox,
                    phase=str(k.get("phase") or ""),
                    mouth_shape=None,
                    notes=str(shot.get("pose") or ""),
                )
            )
        cursor += dur

    contacts: list[ContactMarker] = []
    for c in (contact_lock or {}).get("contacts") or []:
        kind_raw = str(c.get("ir_kind") or c.get("kind") or "impact")
        if kind_raw.startswith("foot"):
            kind = "footstep"
        elif kind_raw == "landing":
            kind = "landing"
        else:
            kind = "impact"
        contacts.append(
            ContactMarker(
                id=str(c.get("id") or f"c-{c.get('shot_id')}-{c.get('frame')}"),
                frame=int(c.get("global_frame") if c.get("global_frame") is not None else c.get("frame") or 0),
                subject_id=str(c.get("subject_id") or "main"),
                label=str(c.get("label") or kind),
                kind=kind,  # type: ignore[arg-type]
            )
        )

    phonemes: list[PhonemeMarker] = []
    for p in (phoneme_sync or {}).get("phonemes") or []:
        audio_f = int(
            p.get("global_audio_frame")
            if p.get("global_audio_frame") is not None
            else p.get("audio_frame")
            or 0
        )
        visual_f = int(
            p.get("global_visual_frame")
            if p.get("global_visual_frame") is not None
            else p.get("visual_frame")
            or 0
        )
        lead = int(p.get("lead_frames") or 2)
        if lead not in (1, 2):
            lead = 2
        if visual_f > audio_f:
            visual_f = max(0, audio_f - lead)
        phonemes.append(
            PhonemeMarker(
                token=str(p.get("token") or "_"),
                shape=str(p.get("shape") or "rest"),
                audio_frame=audio_f,
                visual_frame=visual_f,
                lead_frames=lead,  # type: ignore[arg-type]
            )
        )
        # Mirror mouth shape onto nearest pose key when possible
        if keyframes and str(p.get("shape") or "") not in {"", "rest"}:
            nearest = min(keyframes, key=lambda pk: abs(pk.frame - visual_f))
            # PoseKeyframe is frozen — rebuild list with mouth on matching frame
            keyframes = [
                (
                    pk.model_copy(update={"mouth_shape": str(p.get("shape"))})
                    if pk.frame == nearest.frame and pk.mouth_shape is None
                    else pk
                )
                for pk in keyframes
            ]

    if not keyframes and ir.performance and ir.performance.keyframes:
        keyframes = list(ir.performance.keyframes)
    if total <= 0 and ir.performance:
        total = int(ir.performance.total_frames or 0)

    perf = PerformanceTimeline(
        fps=24,
        total_frames=max(total, len(keyframes)),
        keyframes=keyframes,
        contacts=contacts,
        phonemes=phonemes,
        notes="frame_artifacts_from_props",
    )

    compliance = ir.compliance or empty_compliance_pending()
    flags = (compliance_frame or {}).get("flags") or {}
    if flags:
        compliance = compliance.model_copy(
            update={
                "fps_is_24": bool(flags.get("fps_ok", True)),
                "contact_sounds_match_contact_frames": bool(flags.get("contact_sounds_ok", True)),
                "line_of_action_ok": bool(flags.get("line_180_ok", True)),
                "eyeline_continuity_ok": bool(flags.get("eyeline_ok", True)),
                "notes": "compliance_from_ComplianceFrameAgent",
            }
        )

    notes = list(ir.notes or [])
    if "frame_artifacts=1" not in notes:
        notes.append("frame_artifacts=1")

    return ir.model_copy(
        update={
            "performance": perf,
            "compliance": compliance,
            "notes": notes,
        }
    )


def write_enriched_scene_ir_from_props(
    out_dir: Path | str,
    props: dict[str, Any],
    *,
    brief: str | None = None,
) -> Path:
    """Load or build SceneIR, apply frame artifacts from props, write scene_ir.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "scene_ir.json"
    if path.is_file():
        try:
            ir = SceneIR.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            from scene_ir import empty_scene_ir

            ir = empty_scene_ir(brief or str(props.get("title") or "Story"))
    else:
        # Minimal IR from props shots when chain IR absent
        from scene_ir import empty_scene_ir

        ir = empty_scene_ir(brief or str(props.get("title") or "Story"))
        storyboard = {
            "shots": [
                {
                    "shot_id": s.get("shotId"),
                    "action": s.get("action"),
                    "title": s.get("title"),
                    "story_beat": s.get("storyBeat"),
                    "duration_sec": s.get("durationSec"),
                    "duration_frames": s.get("durationFrames"),
                    "pose": (s.get("craftHints") or {}).get("rig", {}).get("pose"),
                    "verb": s.get("verb"),
                }
                for s in props.get("shots") or []
            ]
        }
        ir = build_scene_ir_from_chain(
            brief or str(props.get("title") or "Story"),
            storyboard=storyboard,
            continuity={
                "180_line_side": (props.get("continuity") or {}).get("lineSide"),
                "approved": (props.get("continuity") or {}).get("approved", True),
                "violations": (props.get("continuity") or {}).get("violations") or [],
            },
            job_out_dir=str(out),
        )

    enriched = apply_frame_artifacts_to_scene_ir(
        ir,
        performance_chart=props.get("performanceChart"),
        contact_lock=props.get("contactLock"),
        phoneme_sync=props.get("phonemeSync"),
        compliance_frame=props.get("complianceFrame"),
    )
    path.write_text(
        enriched.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return path
