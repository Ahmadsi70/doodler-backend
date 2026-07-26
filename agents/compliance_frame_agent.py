"""
ComplianceFrameAgent — real fps / 180° / eyeline flags from props.

Why: PackQualityGate often stubs True; Approve needs falsifiable frame evidence.
"""

from __future__ import annotations

from typing import Any


def run_compliance_frame_agent(
    props: dict[str, Any],
    *,
    expected_fps: int = 24,
) -> dict[str, Any]:
    """
    Emit compliance_frame#v1 from assembled story props / artifacts.
    """
    findings: list[str] = []
    fps = int(props.get("fps") or 0)
    fps_ok = fps == expected_fps
    if not fps_ok:
        findings.append(f"compliance:fps_mismatch:have={fps}:want={expected_fps}")

    cont = props.get("continuity") if isinstance(props.get("continuity"), dict) else {}
    graph = cont.get("graph") if isinstance(cont.get("graph"), dict) else {}
    violations = list(cont.get("violations") or []) + list(graph.get("violations") or [])
    flip_edges = [
        e
        for e in (graph.get("edges") or [])
        if isinstance(e, dict) and e.get("risk") == "screen_direction_flip"
    ]
    line_text = " ".join(str(v).lower() for v in violations)
    line_180_ok = (
        bool(cont.get("approved", True))
        and "180" not in line_text
        and len(flip_edges) == 0
    )
    if not line_180_ok:
        findings.append(
            f"compliance:line_180:approved={cont.get('approved')} flips={len(flip_edges)}"
        )

    nodes = list(graph.get("nodes") or [])
    eyeline_bad = [
        n
        for n in nodes
        if str((n or {}).get("eyeline") or "consistent").lower()
        in {"mismatch", "broken", "fail"}
    ]
    eyeline_ok = len(eyeline_bad) == 0
    if nodes and not eyeline_ok:
        findings.append(f"compliance:eyeline_mismatch:count={len(eyeline_bad)}")
    elif not nodes and cont.get("approved") is False:
        eyeline_ok = False
        findings.append("compliance:eyeline_unknown_without_graph")

    chart = props.get("performanceChart") or props.get("performance_chart") or {}
    chart_shots = list(chart.get("shots") or [])
    chart_present = bool(chart_shots) and all(
        len(s.get("keyframes") or []) >= 2 for s in chart_shots
    )
    if not chart_present:
        findings.append("compliance:performance_chart_thin_or_missing")

    contacts = list((props.get("contactLock") or props.get("contact_lock") or {}).get("contacts") or [])
    contact_present = len(contacts) > 0 or not any(
        str(s.get("pose") or "").lower() in {"walk", "run"} for s in chart_shots
    )
    if not contact_present:
        findings.append("compliance:contacts_missing_for_gait")

    # Check contact→audio alignment for gait shots
    audio_events = list((props.get("audioTimeline") or {}).get("events") or [])
    contact_sounds_ok = True
    gait_shots = [s for s in chart_shots if str(s.get("pose") or "").lower() in {"walk", "run"}]
    if gait_shots and contacts:
        footstep_frames = {
            int(c["global_frame"])
            for c in contacts
            if str(c.get("kind") or "").startswith("foot")
        }
        audio_footstep_frames = {
            int(e.get("startFrame") or 0)
            for e in audio_events
            if "foot" in str(e.get("cue") or "").lower()
        }
        if footstep_frames and audio_footstep_frames:
            matched = sum(1 for f in footstep_frames if any(abs(f - af) <= 2 for af in audio_footstep_frames))
            contact_sounds_ok = matched >= len(footstep_frames) * 0.5
        if not contact_sounds_ok:
            findings.append(f"compliance:contact_audio_mismatch:steps={len(footstep_frames)}:audio_matched={matched}")

    flags = {
        "fps_ok": fps_ok,
        "line_180_ok": line_180_ok,
        "eyeline_ok": eyeline_ok,
        "chart_present": chart_present,
        "contact_present": contact_present,
        "contact_sounds_ok": contact_sounds_ok,
    }
    passed = all(flags.values())
    return {
        "agent": "ComplianceFrameAgent",
        "schema": "compliance_frame#v1",
        "passed": passed,
        "score": round(sum(1 for v in flags.values() if v) / max(1, len(flags)), 3),
        "flags": flags,
        "findings": findings[:16],
        "notes": [f"flags_ok={sum(1 for v in flags.values() if v)}/{len(flags)}"],
    }
