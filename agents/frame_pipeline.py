"""
FramePipeline — orchestrates the 10 frame-level micro-animation agents with
real-time telemetry broadcasting for WebSocket visibility.

Each step emits a ``frame_agent_progress`` event with a ``telemetry`` dict
structured for frontend widget rendering (sliders, toggles, charts).
"""

from __future__ import annotations

import time
from typing import Any, Callable

from chat.message_types import Attachment, MessageStatus


# ── telemetry helpers ───────────────────────────────────────────────────


def _telemetry_event(
    agent: str,
    phase: str,
    status: str,
    summary: str,
    widgets: list[dict[str, Any]] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "frame_agent_progress",
        "agent": agent,
        "phase": phase,
        "status": status,
        "summary": summary,
        "widgets": widgets or [],
        "data": data or {},
        "timestamp": time.time(),
    }


# ── pipeline state ─────────────────────────────────────────────────────


class FramePipelineState:
    """Mutable state shared across frame pipeline steps."""

    def __init__(self, chart_input: list[dict[str, Any]]) -> None:
        self.chart_input: list[dict[str, Any]] = chart_input
        self.performance_chart: dict[str, Any] | None = None
        self.locomotion_cycles: dict[str, Any] | None = None
        self.contact_lock: dict[str, Any] | None = None
        self.acting_lead: dict[str, Any] | None = None
        self.phoneme_sync: dict[str, Any] | None = None
        self.camera_curves: dict[str, Any] | None = None
        self.transition_edges: dict[str, Any] | None = None
        self.audio_plan: dict[str, Any] | None = None
        self.audio_timeline: dict[str, Any] | None = None
        self.foley_timeline: dict[str, Any] | None = None
        self.compliance_frame: dict[str, Any] | None = None
        self.frame_gate: dict[str, Any] | None = None
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_input": self.chart_input,
            "performance_chart": self.performance_chart,
            "locomotion_cycles": self.locomotion_cycles,
            "contact_lock": self.contact_lock,
            "acting_lead": self.acting_lead,
            "phoneme_sync": self.phoneme_sync,
            "camera_curves": self.camera_curves,
            "transition_edges": self.transition_edges,
            "audio_plan": self.audio_plan,
            "audio_timeline": self.audio_timeline,
            "foley_timeline": self.foley_timeline,
            "compliance_frame": self.compliance_frame,
            "frame_gate": self.frame_gate,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FramePipelineState:
        s = cls(d.get("chart_input") or [])
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


# ── individual frame agent steps ───────────────────────────────────────


def step_performance_chart(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.performance_chart_agent import run_performance_chart_agent

    events: list[dict[str, Any]] = []
    try:
        state.performance_chart = run_performance_chart_agent(state.chart_input, fps=24)
        shots = state.performance_chart.get("shots") or []
        events.append(
            _telemetry_event(
                "PerformanceChart",
                "frame_chart",
                "done",
                f"{len(shots)} shot performance charts generated",
                widgets=[{
                    "type": "chart",
                    "label": "Velocity Curves",
                    "data": _velocity_widget_data(shots),
                }],
            )
        )
    except Exception as e:
        state.error = f"PerformanceChart failed: {e}"
        events.append(_telemetry_event("PerformanceChart", "frame_chart", "error", str(e)))
    return events


def step_locomotion_cycle(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.locomotion_cycle_agent import (
        apply_locomotion_to_chart,
        run_locomotion_cycle_agent,
    )

    events: list[dict[str, Any]] = []
    try:
        state.locomotion_cycles = run_locomotion_cycle_agent(
            state.chart_input, performance_chart=state.performance_chart, fps=24
        )
        state.performance_chart = apply_locomotion_to_chart(
            state.performance_chart, state.locomotion_cycles
        )
        cycles = state.locomotion_cycles.get("cycles") or []
        events.append(
            _telemetry_event(
                "LocomotionCycle",
                "frame_locomotion",
                "done",
                f"{len(cycles)} gait cycles applied",
                widgets=[{
                    "type": "toggle",
                    "label": "Gait Cycles",
                    "options": [{"id": c.get("id"), "label": c.get("gait", "walk")} for c in cycles[:8]],
                }],
            )
        )
    except Exception as e:
        state.error = f"LocomotionCycle failed: {e}"
        events.append(_telemetry_event("LocomotionCycle", "frame_locomotion", "error", str(e)))
    return events


def step_contact_lock(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.contact_lock_agent import run_contact_lock_agent

    events: list[dict[str, Any]] = []
    try:
        state.contact_lock = run_contact_lock_agent(
            state.chart_input, performance_chart=state.performance_chart, fps=24
        )
        contacts = state.contact_lock.get("contacts") or []
        events.append(
            _telemetry_event(
                "ContactLock",
                "frame_contact",
                "done",
                f"{len(contacts)} contact markers locked",
                widgets=[{
                    "type": "toggle",
                    "label": "Contact Frames",
                    "options": [
                        {"id": c.get("id"), "label": f"Shot {c.get('shot_id')} f{c.get('frame')}: {c.get('kind')}"}
                        for c in contacts[:12]
                    ],
                }],
            )
        )
    except Exception as e:
        state.error = f"ContactLock failed: {e}"
        events.append(_telemetry_event("ContactLock", "frame_contact", "error", str(e)))
    return events


def step_acting_lead(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.acting_lead_agent import (
        apply_acting_lead_to_chart,
        run_acting_lead_agent,
    )

    events: list[dict[str, Any]] = []
    try:
        state.acting_lead = run_acting_lead_agent(
            state.chart_input, performance_chart=state.performance_chart, fps=24
        )
        state.performance_chart = apply_acting_lead_to_chart(
            state.performance_chart, state.acting_lead
        )
        markers = state.acting_lead.get("markers") or []
        events.append(
            _telemetry_event(
                "ActingLead",
                "frame_acting",
                "done",
                f"{len(markers)} eyes-lead markers applied",
                widgets=[{
                    "type": "slider",
                    "label": "Eyes Lead (frames)",
                    "min": 1,
                    "max": 6,
                    "value": 2,
                    "step": 1,
                }],
            )
        )
    except Exception as e:
        state.error = f"ActingLead failed: {e}"
        events.append(_telemetry_event("ActingLead", "frame_acting", "error", str(e)))
    return events


def step_phoneme_sync(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.phoneme_sync_agent import run_phoneme_sync_agent

    events: list[dict[str, Any]] = []
    try:
        state.phoneme_sync = run_phoneme_sync_agent(state.chart_input, fps=24, lead_frames=2)
        curves = state.phoneme_sync.get("curves") or []
        events.append(
            _telemetry_event(
                "PhonemeSync",
                "frame_phoneme",
                "done",
                f"{len(curves)} viseme curves generated",
                widgets=[{
                    "type": "chart",
                    "label": "Mouth Curves",
                    "data": _mouth_widget_data(curves),
                }],
            )
        )
    except Exception as e:
        state.error = f"PhonemeSync failed: {e}"
        events.append(_telemetry_event("PhonemeSync", "frame_phoneme", "error", str(e)))
    return events


def step_camera_curve(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.camera_curve_agent import run_camera_curve_agent

    events: list[dict[str, Any]] = []
    try:
        state.camera_curves = run_camera_curve_agent(state.chart_input, fps=24)
        curves = state.camera_curves.get("curves") or []
        events.append(
            _telemetry_event(
                "CameraCurve",
                "frame_camera",
                "done",
                f"{len(curves)} camera curves computed",
                widgets=[{
                    "type": "chart",
                    "label": "Camera Curves",
                    "data": _camera_widget_data(curves),
                }],
            )
        )
    except Exception as e:
        state.error = f"CameraCurve failed: {e}"
        events.append(_telemetry_event("CameraCurve", "frame_camera", "error", str(e)))
    return events


def step_transition_edge(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.transition_edge_agent import run_transition_edge_agent

    events: list[dict[str, Any]] = []
    try:
        state.transition_edges = run_transition_edge_agent(state.chart_input, fps=24)
        edges = state.transition_edges.get("edges") or []
        events.append(
            _telemetry_event(
                "TransitionEdge",
                "frame_transition",
                "done",
                f"{len(edges)} transition edges resolved",
                widgets=[{
                    "type": "toggle",
                    "label": "Cut Types",
                    "options": [{"id": str(i), "label": f"Shot {e.get('from')}→{e.get('to')}: {e.get('transition', 'cut')}"} for i, e in enumerate(edges[:10])],
                }],
            )
        )
    except Exception as e:
        state.error = f"TransitionEdge failed: {e}"
        events.append(_telemetry_event("TransitionEdge", "frame_transition", "error", str(e)))
    return events


def step_audio(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.audio_cue_agent import run_audio_cue_agent
    from agents.foley_timeline_agent import run_foley_timeline_agent
    from tools.audio_cues import build_audio_timeline_from_plan, sync_cues_to_remotion_public

    events: list[dict[str, Any]] = []
    try:
        emotion = "neutral"
        state.audio_plan = run_audio_cue_agent(
            state.chart_input,
            fps=24,
            emotion=emotion,
            contacts=state.contact_lock.get("contacts") if state.contact_lock else None,
        )
        state.audio_timeline = build_audio_timeline_from_plan(
            state.audio_plan, state.chart_input, fps=24
        )
        state.foley_timeline = run_foley_timeline_agent(
            state.chart_input,
            contacts=state.contact_lock.get("contacts") if state.contact_lock else None,
            fps=24,
        )
        from tools.audio_cues import merge_foley_into_audio_timeline

        state.audio_timeline = merge_foley_into_audio_timeline(
            state.audio_timeline, state.foley_timeline
        )
        sync_cues_to_remotion_public()
        events.append(
            _telemetry_event(
                "AudioCue",
                "frame_audio",
                "done",
                "Audio + Foley timeline assembled",
                widgets=[{"type": "toggle", "label": "Audio Events", "options": [{"id": f"evt_{i}", "label": str(e)} for i, e in enumerate((state.audio_timeline.get("events") or [])[:8])]}],
            )
        )
    except Exception as e:
        state.error = f"Audio pipeline failed: {e}"
        events.append(_telemetry_event("AudioCue", "frame_audio", "error", str(e)))
    return events


def step_frame_gate(state: FramePipelineState) -> list[dict[str, Any]]:
    from tools.frame_gate import run_frame_gate

    events: list[dict[str, Any]] = []
    try:
        state.frame_gate = run_frame_gate(
            {
                "performanceChart": state.performance_chart,
                "contactLock": state.contact_lock,
                "locomotionCycles": state.locomotion_cycles,
            },
            strict=False,
        )
        passed = state.frame_gate.get("passed", False)
        events.append(
            _telemetry_event(
                "FrameGate",
                "frame_gate",
                "done",
                f"Frame gate {'PASSED' if passed else 'FAILED'}",
                widgets=[{
                    "type": "toggle",
                    "label": "Gate Result",
                    "options": [{"id": "pass", "label": f"Passed: {passed} | Score: {state.frame_gate.get('score', 0)}"}],
                }],
            )
        )
    except Exception as e:
        state.error = f"FrameGate failed: {e}"
        events.append(_telemetry_event("FrameGate", "frame_gate", "error", str(e)))
    return events


def step_compliance(state: FramePipelineState) -> list[dict[str, Any]]:
    from agents.compliance_frame_agent import run_compliance_frame_agent

    events: list[dict[str, Any]] = []
    try:
        props_stub = {
            "fps": 24,
            "continuity": {},
            "performanceChart": state.performance_chart,
            "shots": state.chart_input,
        }
        state.compliance_frame = run_compliance_frame_agent(props_stub, expected_fps=24)
        findings = state.compliance_frame.get("findings") or []
        events.append(
            _telemetry_event(
                "ComplianceFrame",
                "frame_compliance",
                "done",
                f"{len(findings)} compliance checks run",
                widgets=[{
                    "type": "toggle",
                    "label": "Compliance Findings",
                    "options": [{"id": f"f_{i}", "label": str(f)} for i, f in enumerate(findings[:8])],
                }],
            )
        )
    except Exception as e:
        state.error = f"ComplianceFrame failed: {e}"
        events.append(_telemetry_event("ComplianceFrame", "frame_compliance", "error", str(e)))
    return events


# ── widget data helpers ────────────────────────────────────────────────


def _velocity_widget_data(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract per-shot joint velocity summary for chart widgets."""
    out = []
    for s in shots[:6]:
        sid = s.get("shot_id", 0)
        dur = s.get("duration_frames", 24)
        out.append({
            "shotId": sid,
            "durationFrames": dur,
            "pelvisY": round(s.get("joints", {}).get("pelvisY", 0), 3),
            "headY": round(s.get("joints", {}).get("headY", 0), 3),
        })
    return out


def _mouth_widget_data(curves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract mouth openness per shot for viseme chart."""
    out = []
    for c in curves[:6]:
        out.append({
            "shotId": c.get("shot_id", 0),
            "mouthOpen": round(c.get("mouthOpen", 0), 3),
            "frames": c.get("frames", 0),
        })
    return out


def _camera_widget_data(curves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract camera keyframe endpoints for chart widget."""
    out = []
    for c in curves[:6]:
        kfs = c.get("keyframes") or []
        out.append({
            "shotId": c.get("shot_id", 0),
            "keyframes": [{"frame": k.get("frame"), "scale": k.get("scale")} for k in kfs[:4]],
        })
    return out


# ── pipeline orchestrator ──────────────────────────────────────────────


def build_chart_input(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build chart_input from enriched shot dicts (mirrors remotion_emitter logic)."""
    chart_input = []
    for s in shots:
        sfx = list(s.get("sfx") or [])
        chart_input.append({
            "shot_id": s.get("shotId"),
            "story_beat": s.get("storyBeat"),
            "pose": (s.get("craftHints") or {}).get("rig", {}).get("pose") or "idle",
            "expression": (s.get("craftHints") or {}).get("rig", {}).get("expression"),
            "action": s.get("action"),
            "dialogue": s.get("dialogue") or "",
            "vo_path": s.get("voPath") or "",
            "duration_frames": s.get("durationFrames"),
            "anticipation_frames": s.get("anticipationFrames"),
            "hold_frames": s.get("holdFrames"),
            "camera": s.get("camera"),
            "camera_move": s.get("cameraMove"),
            "sfx": sfx,
        })
    return chart_input


StepHandler = Callable[[FramePipelineState], list[dict[str, Any]]]

_STEPS: list[tuple[str, str, StepHandler]] = [
    ("PerformanceChart", "frame_chart", step_performance_chart),
    ("LocomotionCycle", "frame_locomotion", step_locomotion_cycle),
    ("ContactLock", "frame_contact", step_contact_lock),
    ("ActingLead", "frame_acting", step_acting_lead),
    ("PhonemeSync", "frame_phoneme", step_phoneme_sync),
    ("CameraCurve", "frame_camera", step_camera_curve),
    ("TransitionEdge", "frame_transition", step_transition_edge),
    ("AudioCue+Foley", "frame_audio", step_audio),
    ("ComplianceFrame", "frame_compliance", step_compliance),
    ("FrameGate", "frame_gate", step_frame_gate),
]


def run_frame_pipeline(
    chart_input: list[dict[str, Any]],
    *,
    broadcast: Callable[[dict[str, Any]], None] | None = None,
    session_id: str = "",
) -> tuple[FramePipelineState, list[dict[str, Any]]]:
    """Run all frame pipeline steps sequentially, broadcasting telemetry."""
    state = FramePipelineState(chart_input)
    all_events: list[dict[str, Any]] = []

    for name, phase, step_fn in _STEPS:
        if broadcast:
            broadcast({
                "type": "frame_agent_progress",
                "agent": name,
                "phase": phase,
                "status": "working",
                "summary": f"Running {name}...",
                "timestamp": time.time(),
                "session_id": session_id,
            })
        step_events = step_fn(state)
        all_events.extend(step_events)
        for ev in step_events:
            ev["session_id"] = session_id
            if broadcast:
                broadcast(ev)

        if state.error:
            break

    return state, all_events
