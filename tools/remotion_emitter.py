"""Generate ``story_props.json`` — the data contract consumed by Remotion compositions.

This is the ONLY output this module produces. Code (not video) is the deliverable;
users copy the Remotion project and run ``npm install && npx remotion render`` themselves.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_REMOTION = _ROOT / "remotion"


_GRADE_PALETTES: dict[str, dict[str, str]] = {
    "pastel_muted": {
        "bg0": "#e8dfe8",
        "bg1": "#c5d4e8",
        "bg2": "#9eb8d4",
        "accent": "#7a9eb8",
        "text": "#2a3344",
        "muted": "#5a6a7a",
    },
    "moody_teal_orange": {
        "bg0": "#0d1b1e",
        "bg1": "#1a3338",
        "bg2": "#0a1214",
        "accent": "#e07a3d",
        "text": "#e8f0f2",
        "muted": "#8aa4a8",
    },
    "clean_corporate": {
        "bg0": "#f4f6f8",
        "bg1": "#dde3ea",
        "bg2": "#c5ced8",
        "accent": "#3d5a80",
        "text": "#1b2430",
        "muted": "#5c6b7a",
    },
    "vivid_pop": {
        "bg0": "#1a1028",
        "bg1": "#3a2060",
        "bg2": "#12081c",
        "accent": "#ff6bcb",
        "text": "#f8f0ff",
        "muted": "#b8a0d0",
    },
}


def _palette_for_grade(grade: str | None) -> dict[str, str]:
    try:
        from tools.craft_packs import load_look_bible

        look = load_look_bible()
        row = (look.get("grades") or {}).get(grade or "")
        if isinstance(row, dict) and row.get("bg0"):
            return {
                "bg0": str(row["bg0"]),
                "bg1": str(row.get("bg1") or row["bg0"]),
                "bg2": str(row.get("bg2") or row["bg0"]),
                "accent": str(row.get("accent") or "#7a9eb8"),
                "text": str(row.get("text") or "#2a3344"),
                "muted": str(row.get("muted") or "#5a6a7a"),
            }
    except Exception:  # noqa: BLE001
        pass
    if grade and grade in _GRADE_PALETTES:
        return dict(_GRADE_PALETTES[grade])
    return dict(_GRADE_PALETTES["pastel_muted"])


def write_story_composition_props(
    out_dir: Path | str,
    *,
    storyboard: dict[str, Any],
    cinematography: dict[str, Any] | None = None,
    timing: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    character_path: str | Path | None = None,
    character_rig: dict[str, Any] | None = None,
    character_layers: dict[str, Any] | None = None,
    title: str = "Story",
    sync_remotion_public: bool = True,
    frame_pipeline_state: dict[str, Any] | None = None,
) -> Path:
    """Write ``story_props.json`` consumed by Remotion Composition."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shots_in = storyboard.get("shots") or []
    timing_by = {
        s.get("shot_id"): s for s in (timing or {}).get("shots") or []
    }
    cine_by = {
        f.get("shot_id"): f for f in (cinematography or {}).get("frames") or []
    }
    cont = continuity or {}
    # Ensure continuity graph exists for props contract
    if not isinstance(cont.get("graph"), dict):
        try:
            from tools.continuity_graph import (
                build_continuity_graph,
                merge_graph_into_continuity,
            )

            graph = build_continuity_graph(
                storyboard=storyboard,
                cinematography=cinematography,
                continuity=cont,
            )
            cont = merge_graph_into_continuity(cont, graph)
        except Exception:  # noqa: BLE001
            pass
    graph = cont.get("graph") if isinstance(cont.get("graph"), dict) else {}
    edge_by_to = {
        e.get("to"): e for e in (graph.get("edges") or []) if isinstance(e, dict)
    }
    style = style_profile or {}
    eng = style.get("engine") if isinstance(style.get("engine"), dict) else {}
    grade = str(
        style.get("grade_preset") or eng.get("grade") or "pastel_muted"
    )
    pace = str(eng.get("pace") or style.get("pace") or "measured")
    camera_preset = str(eng.get("camera") or style.get("camera_preset") or "locked_symmetric")
    # Williams craft do/dont → Remotion craftHints
    behavior_by_id: dict[str, Any] = {}
    behavior_by_beat: dict[str, Any] = {}
    try:
        from tools.williams_craft import load_williams_craft_pack

        pack = load_williams_craft_pack()
        for b in pack.shot_behaviors:
            bid = str(b.get("id") or "")
            beat = str(b.get("story_beat") or "")
            if bid:
                behavior_by_id[bid] = b
            if beat and beat not in behavior_by_beat:
                behavior_by_beat[beat] = b
    except Exception:  # noqa: BLE001
        pass

    try:
        from tools.craft_packs import (
            camera_move_for_beat,
            look_for_beat,
            resolve_transition,
            shot_size_scale,
        )
    except ImportError:
        from .craft_packs import (  # type: ignore
            camera_move_for_beat,
            look_for_beat,
            resolve_transition,
            shot_size_scale,
        )

    shots = []
    prev_beat = ""
    for sh in shots_in:
        sid = sh.get("shot_id")
        trow = timing_by.get(sid) or {}
        crow = cine_by.get(sid) or {}
        dur = float(
            trow.get("duration_sec")
            if trow.get("duration_sec") is not None
            else sh.get("duration_sec")
            or 3.0
        )
        composition = str(crow.get("composition") or sh.get("composition_shape") or "C").upper()
        # Glebas-style thirds: L → left third, R → right, C → center
        if composition.startswith("L"):
            thirds_x = 0.33
        elif composition.startswith("R"):
            thirds_x = 0.67
        else:
            thirds_x = 0.5
        look_raw = str(crow.get("look_space_direction") or "").lower()
        if look_raw in {"left", "right"}:
            look_space = look_raw
        else:
            look_space = (
                "right"
                if thirds_x <= 0.4
                else ("left" if thirds_x >= 0.6 else "center")
            )
        beat = str(sh.get("story_beat") or trow.get("williams_story_beat") or "")
        bid = str(
            trow.get("williams_behavior_id")
            or crow.get("williams_behavior_id")
            or ""
        )
        behavior = behavior_by_id.get(bid) or behavior_by_beat.get(beat)
        # Default pose from beat when craft pack omits rig
        default_pose = {
            "entrance": "walk",
            "exit": "walk",
            "reaction": "react",
            "reveal": "walk",
            "quiet_hold": "idle",
            "conflict": "react",
            "decision": "idle",
        }.get(beat, "idle")
        rig_hint = dict((behavior or {}).get("rig") or {})
        # Code-first StudioSpec / timing author fields win over pack defaults
        if isinstance(trow.get("williams_rig"), dict):
            rig_hint = {**rig_hint, **trow["williams_rig"]}
        if sh.get("pose"):
            rig_hint["pose"] = sh.get("pose")
        if sh.get("expression"):
            rig_hint["expression"] = sh.get("expression")
        pose = str(rig_hint.get("pose") or default_pose)
        expression = str(rig_hint.get("expression") or "neutral")
        craft_hints = {
            "id": (behavior or {}).get("id"),
            "do": list((behavior or {}).get("do") or [])[:4],
            "dont": list((behavior or {}).get("dont") or [])[:4],
            "rig": {"pose": pose, "expression": expression},
            "actionBias": ((behavior or {}).get("timing") or {}).get("actionBias")
            or "even",
        }
        try:
            from tools.pose_presets import bake_shot_rig, env_profile_for_beat
        except ImportError:
            from .pose_presets import bake_shot_rig, env_profile_for_beat  # type: ignore

        shot_rig = bake_shot_rig(
            pose=pose,
            expression=expression,
            base_rig=character_rig if isinstance(character_rig, dict) else None,
            fps=24,
        )
        env_profile = env_profile_for_beat(beat, str(crow.get("lighting") or ""))
        cam_name = str(crow.get("camera") or "static")
        camera_move = camera_move_for_beat(beat, cam_name)
        shot_size = str(
            crow.get("shot_size") or sh.get("shot_size") or "MS"
        ).upper()
        look = look_for_beat(beat, fallback_grade=grade)
        # Prefer look palette vignette into env when present
        if look.get("vignette") is not None:
            env_profile = {**env_profile, "vignette": float(look["vignette"])}
        if look.get("parallax") is not None:
            env_profile = {**env_profile, "parallax": float(look["parallax"])}
        if look.get("depthLayers") is not None:
            env_profile = {
                **env_profile,
                "depthLayers": int(look["depthLayers"]),
            }
        blink_every = 36
        try:
            from tools.pose_presets import load_performance_bible

            bible = load_performance_bible()
            pose_row = (bible.get("poses") or {}).get(pose) or {}
            blink_every = int(pose_row.get("blink_every_frames") or blink_every)
        except Exception:  # noqa: BLE001
            pass
        edge = edge_by_to.get(sid) or {}
        transition_id = str(edge.get("transition") or "")
        if not transition_id:
            transition_id = resolve_transition(prev_beat, beat).get("id") or "crossfade"
        transition_meta = resolve_transition(prev_beat, beat)
        if edge.get("transition"):
            try:
                from tools.craft_packs import load_transition_grammar

                g = load_transition_grammar()
                transition_meta = dict(
                    (g.get("transitions") or {}).get(transition_id)
                    or transition_meta
                )
                transition_meta["id"] = transition_id
            except Exception:  # noqa: BLE001
                transition_meta["id"] = transition_id
        shots.append(
            {
                "shotId": sid,
                "title": sh.get("title") or f"Shot {sid}",
                "action": sh.get("action") or sh.get("idea") or "",
                "durationSec": dur,
                "durationFrames": int(
                    trow.get("duration_frames") or max(12, round(dur * 24))
                ),
                "holdFrames": int(trow.get("hold_frames") or 12),
                "anticipationFrames": int(trow.get("anticipation_frames") or 6),
                "dialogue": str(sh.get("dialogue") or ""),
                "voPath": str(sh.get("vo_path") or sh.get("voPath") or ""),
                "lens": crow.get("lens") or "standard",
                "camera": cam_name,
                "cameraMove": camera_move,
                "shotSize": shot_size,
                "shotSizeScale": shot_size_scale(shot_size),
                "composition": composition[:1] or "C",
                "lighting": crow.get("lighting") or "three_point",
                "thirdsX": thirds_x,
                "lookSpace": look_space,
                "verb": sh.get("verb"),
                "storyBeat": beat or None,
                "sfx": list(sh.get("sfx") or []),
                "craftHints": craft_hints,
                "envProfile": env_profile,
                "shotRig": shot_rig,
                "look": look,
                "blinkEveryFrames": blink_every,
                "captionMode": "lower_third",
                "transitionIn": {
                    "id": transition_meta.get("id") or "crossfade",
                    "frames": int(transition_meta.get("frames") or 12),
                    "opacity": bool(transition_meta.get("opacity", True)),
                    "slide": bool(transition_meta.get("slide", True)),
                },
            }
        )
        prev_beat = beat

    # ── Frame agents ────────────────────────────────────────────────
    # Frame agents P0–P2: chart → loco → contact → lead → camera → edges → audio/foley → gates
    # When frame_pipeline_state is provided, use pre-computed artifacts.
    fps_local = 24
    performance_chart: dict[str, Any] | None = None
    contact_lock: dict[str, Any] | None = None
    locomotion_cycles: dict[str, Any] | None = None
    camera_curves: dict[str, Any] | None = None
    transition_edges: dict[str, Any] | None = None
    foley_timeline: dict[str, Any] | None = None
    acting_lead: dict[str, Any] | None = None
    phoneme_sync: dict[str, Any] | None = None
    compliance_frame: dict[str, Any] | None = None
    frame_gate: dict[str, Any] | None = None
    audio_timeline: dict[str, Any] | None = None
    _frame_agent_error: str | None = None

    if frame_pipeline_state:
        fps_local = frame_pipeline_state.get("fps", 24)
        performance_chart = frame_pipeline_state.get("performance_chart")
        contact_lock = frame_pipeline_state.get("contact_lock")
        locomotion_cycles = frame_pipeline_state.get("locomotion_cycles")
        camera_curves = frame_pipeline_state.get("camera_curves")
        transition_edges = frame_pipeline_state.get("transition_edges")
        foley_timeline = frame_pipeline_state.get("foley_timeline")
        acting_lead = frame_pipeline_state.get("acting_lead")
        phoneme_sync = frame_pipeline_state.get("phoneme_sync")
        compliance_frame = frame_pipeline_state.get("compliance_frame")
        frame_gate = frame_pipeline_state.get("frame_gate")
        audio_timeline = frame_pipeline_state.get("audio_timeline")
        _frame_agent_error = frame_pipeline_state.get("error")
        # Apply pre-computed artifacts to shots
        if performance_chart:
            try:
                from agents.performance_chart_agent import chart_shot_to_rig
                from agents.camera_curve_agent import curve_for_shot
                from agents.transition_edge_agent import transition_in_for_shot
                from agents.acting_lead_agent import expression_curve_for_shot
                from agents.phoneme_sync_agent import mouth_curve_for_shot, merge_mouth_into_expression_curve

                chart_by_id = {s.get("shot_id"): s for s in performance_chart.get("shots") or []}
                for s in shots:
                    ch = chart_by_id.get(s.get("shotId"))
                    if ch:
                        s["shotRig"] = chart_shot_to_rig(ch, fps=24)
                        s["performancePhases"] = {"ant_end": ch.get("ant_end"), "hold_start": ch.get("hold_start")}
                    curve = curve_for_shot(camera_curves, s.get("shotId"))
                    if curve:
                        s["cameraCurve"] = curve
                    tin = transition_in_for_shot(transition_edges, s.get("shotId"))
                    if tin:
                        s["transitionIn"] = tin
                    expr_c = expression_curve_for_shot(acting_lead, performance_chart, s.get("shotId"))
                    mouth_c = mouth_curve_for_shot(phoneme_sync, s.get("shotId"))
                    merged = merge_mouth_into_expression_curve(expr_c, mouth_c)
                    if merged:
                        s["expressionCurve"] = merged
            except Exception:
                pass

    if not frame_pipeline_state:
        # Compute frame artifacts inline (backward-compatible path)
        try:
            from agents.performance_chart_agent import (
                chart_shot_to_rig,
                run_performance_chart_agent,
            )
            from agents.contact_lock_agent import run_contact_lock_agent
            from agents.locomotion_cycle_agent import (
                apply_locomotion_to_chart,
                run_locomotion_cycle_agent,
            )
            from agents.camera_curve_agent import curve_for_shot, run_camera_curve_agent
            from agents.transition_edge_agent import (
                run_transition_edge_agent,
                transition_in_for_shot,
            )
            from agents.foley_timeline_agent import (
                merge_foley_into_audio_timeline,
                run_foley_timeline_agent,
            )
            from agents.acting_lead_agent import (
                apply_acting_lead_to_chart,
                expression_curve_for_shot,
                run_acting_lead_agent,
            )
            from agents.phoneme_sync_agent import (
                merge_mouth_into_expression_curve,
                mouth_curve_for_shot,
                run_phoneme_sync_agent,
            )
            from agents.compliance_frame_agent import run_compliance_frame_agent
            from agents.audio_cue_agent import run_audio_cue_agent
            from tools.audio_cues import build_audio_timeline_from_plan, sync_cues_to_remotion_public
            from tools.frame_gate import run_frame_gate

            chart_input = []
            for s in shots:
                sfx = list(s.get("sfx") or [])
                if not sfx:
                    try:
                        from agents.audio_cue_agent import load_audio_catalog
                        from agents.sfx_plan import infer_sfx_events
                        from tools.audio_cues import ensure_audio_cue_files

                        ensure_audio_cue_files()
                        sfx = infer_sfx_events(
                            str(s.get("action") or ""),
                            beat=str(s.get("storyBeat") or ""),
                            catalog_cues=dict(load_audio_catalog().get("cues") or {}),
                        )
                    except Exception:  # noqa: BLE001
                        sfx = []
                chart_input.append(
                    {
                        "shot_id": s.get("shotId"),
                        "story_beat": s.get("storyBeat"),
                        "pose": (s.get("craftHints") or {}).get("rig", {}).get("pose")
                        or "idle",
                        "expression": (s.get("craftHints") or {}).get("rig", {}).get(
                            "expression"
                        )
                        or "neutral",
                        "action": s.get("action"),
                        "dialogue": s.get("dialogue") or "",
                        "vo_path": s.get("voPath") or "",
                        "duration_frames": s.get("durationFrames"),
                        "anticipation_frames": s.get("anticipationFrames"),
                        "hold_frames": s.get("holdFrames"),
                        "camera": s.get("camera"),
                        "camera_move": s.get("cameraMove"),
                        "sfx": sfx,
                    }
                )
            # Resolve VO wav durations before phoneme sync
            try:
                from tools.vo_audio import (
                    duration_frames_for_wav,
                    sync_vo_to_remotion_public,
                    vo_audio_event,
                )

                for row in chart_input:
                    vp = str(row.get("vo_path") or "")
                    if vp and Path(vp).is_file():
                        row["vo_duration_frames"] = duration_frames_for_wav(vp, fps=24)
            except Exception:  # noqa: BLE001
                pass
            performance_chart = run_performance_chart_agent(chart_input, fps=24)
            locomotion_cycles = run_locomotion_cycle_agent(
                chart_input, performance_chart=performance_chart, fps=24
            )
            performance_chart = apply_locomotion_to_chart(performance_chart, locomotion_cycles)
            contact_lock = run_contact_lock_agent(
                chart_input, performance_chart=performance_chart, fps=24
            )
            acting_lead = run_acting_lead_agent(
                chart_input, performance_chart=performance_chart, fps=24
            )
            performance_chart = apply_acting_lead_to_chart(performance_chart, acting_lead)
            phoneme_sync = run_phoneme_sync_agent(chart_input, fps=24, lead_frames=2)
            camera_curves = run_camera_curve_agent(chart_input, fps=24)
            transition_edges = run_transition_edge_agent(
                chart_input, continuity_graph=graph if isinstance(graph, dict) else None, fps=24
            )
            chart_by_id = {s.get("shot_id"): s for s in performance_chart.get("shots") or []}
            for s in shots:
                ch = chart_by_id.get(s.get("shotId"))
                if ch:
                    s["shotRig"] = chart_shot_to_rig(ch, fps=24)
                    s["performancePhases"] = {
                        "ant_end": ch.get("ant_end"),
                        "hold_start": ch.get("hold_start"),
                    }
                curve = curve_for_shot(camera_curves, s.get("shotId"))
                if curve:
                    s["cameraCurve"] = curve
                tin = transition_in_for_shot(transition_edges, s.get("shotId"))
                if tin:
                    s["transitionIn"] = tin
                expr_c = expression_curve_for_shot(
                    acting_lead, performance_chart, s.get("shotId")
                )
                mouth_c = mouth_curve_for_shot(phoneme_sync, s.get("shotId"))
                merged = merge_mouth_into_expression_curve(expr_c, mouth_c)
                if merged:
                    s["expressionCurve"] = merged
            plan = run_audio_cue_agent(
                chart_input,
                fps=24,
                emotion=str(style.get("emotion") or pace or "neutral"),
                contacts=contact_lock.get("contacts"),
            )
            audio_timeline = build_audio_timeline_from_plan(plan, shots, fps=24)
            foley_timeline = run_foley_timeline_agent(
                chart_input, contacts=contact_lock.get("contacts"), fps=24
            )
            audio_timeline = merge_foley_into_audio_timeline(audio_timeline, foley_timeline)
            # Append VO wav events (cursor = shot start)
            try:
                from tools.vo_audio import (
                    duration_frames_for_wav,
                    sync_vo_to_remotion_public,
                    vo_audio_event,
                )

                cursor = 0
                events = list(audio_timeline.get("events") or [])
                for row, s in zip(chart_input, shots):
                    vp = str(row.get("vo_path") or "")
                    dur = int(s.get("durationFrames") or 0)
                    if vp and Path(vp).is_file():
                        rel = sync_vo_to_remotion_public(vp, shot_id=s.get("shotId"))
                        ant = int(s.get("anticipationFrames") or 6)
                        vdur = int(row.get("vo_duration_frames") or duration_frames_for_wav(vp, fps=24))
                        events.append(
                            vo_audio_event(
                                shot_id=s.get("shotId"),
                                start_frame=cursor + ant,
                                file_rel=rel,
                                duration_frames=vdur,
                            )
                        )
                        s["voFile"] = rel
                        s["voDurationFrames"] = vdur
                    cursor += dur
                audio_timeline["events"] = events
            except Exception:  # noqa: BLE001
                pass
            sync_cues_to_remotion_public()
            frame_gate = run_frame_gate(
                {
                    "performanceChart": performance_chart,
                    "contactLock": contact_lock,
                    "locomotionCycles": locomotion_cycles,
                },
                strict=False,
            )
        except Exception as exc:  # noqa: BLE001
            import traceback as _tb
            _frame_agent_error = f"{type(exc).__name__}: {exc}"
            _frame_agent_traceback = _tb.format_exc()[-800:]
            performance_chart = None
            contact_lock = None
            locomotion_cycles = None
            camera_curves = None
            transition_edges = None
            foley_timeline = None
            acting_lead = None
            phoneme_sync = None
            compliance_frame = None
            frame_gate = None
            try:
                from tools.audio_cues import build_audio_timeline, sync_cues_to_remotion_public

                audio_timeline = build_audio_timeline(shots, fps=24)
                sync_cues_to_remotion_public()
            except Exception:  # noqa: BLE001
                audio_timeline = {
                    "schema": "audio_timeline#v1",
                    "fps": 24,
                    "events": [],
                    "totalFrames": 0,
                }

    layers_out: dict[str, str] | None = None
    if isinstance(character_layers, dict):
        pub_layers = _REMOTION / "public" / "layers"
        pub_layers.mkdir(parents=True, exist_ok=True)
        layers_out = {}
        for key in ("body", "head", "hand"):
            src = character_layers.get(key)
            if not src:
                continue
            sp = Path(str(src))
            if not sp.is_file():
                continue
            dest = pub_layers / f"{key}{sp.suffix.lower() or '.png'}"
            shutil.copy2(sp, dest)
            layers_out[key] = f"layers/{dest.name}"

    props = {
        "title": title,
        "fps": 24,
        "visualVersion": 3,
        "styleId": style.get("style_id") or "symmetrical_pastel_cinema",
        "grade": grade,
        "pace": pace,
        "cameraPreset": camera_preset,
        "palette": _palette_for_grade(grade),
        "continuity": {
            "lineSide": cont.get("180_line_side") or "left",
            "approved": bool(cont.get("approved", True)),
            "violations": list(cont.get("violations") or []),
            "graph": graph if isinstance(graph, dict) else cont.get("graph"),
        },
        "characterPath": str(character_path) if character_path else None,
        "characterRig": character_rig,
        "characterLayers": layers_out,
        "audioTimeline": audio_timeline,
        "performanceChart": performance_chart,
        "contactLock": contact_lock,
        "locomotionCycles": locomotion_cycles,
        "cameraCurves": camera_curves,
        "transitionEdges": transition_edges,
        "foleyTimeline": foley_timeline,
        "actingLead": acting_lead,
        "phonemeSync": phoneme_sync,
        "frameGate": frame_gate,
        "shots": shots,
    }
    if performance_chart is None:
        props["_frameAgentWarning"] = _frame_agent_error
    try:
        from agents.compliance_frame_agent import run_compliance_frame_agent

        props["complianceFrame"] = run_compliance_frame_agent(props)
    except Exception:  # noqa: BLE001
        props["complianceFrame"] = compliance_frame
    path = out / "story_props.json"
    path.write_text(json.dumps(props, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Phase 1: SceneIR audit bridge gets same frame artifacts
    try:
        from tools.scene_ir_builder import write_enriched_scene_ir_from_props

        write_enriched_scene_ir_from_props(out, props, brief=title)
    except Exception:  # noqa: BLE001
        pass
    if sync_remotion_public:
        pub = _REMOTION / "public"
        pub.mkdir(parents=True, exist_ok=True)
        (pub / "story_props.json").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        if character_path and Path(character_path).is_file():
            dest = pub / "character.png"
            shutil.copy2(character_path, dest)
            props["characterPath"] = "character.png"
            path.write_text(
                json.dumps(props, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            (pub / "story_props.json").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            try:
                from tools.scene_ir_builder import write_enriched_scene_ir_from_props

                write_enriched_scene_ir_from_props(out, props, brief=title)
            except Exception:  # noqa: BLE001
                pass
    return path


