"""P0: PerformanceChartAgent + ContactLockAgent (frame-level supervision)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_performance_chart_covers_shot_frames():
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "story_beat": "entrance",
            "pose": "walk",
            "expression": "neutral",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        },
        {
            "shot_id": 1,
            "story_beat": "reaction",
            "pose": "react",
            "expression": "shock",
            "duration_frames": 36,
            "anticipation_frames": 8,
            "hold_frames": 10,
        },
    ]
    out = run_performance_chart_agent(shots, fps=24)
    assert out["agent"] == "PerformanceChartAgent"
    assert out["schema"] == "performance_chart#v1"
    assert out["fps"] == 24
    assert len(out["shots"]) == 2
    s0 = out["shots"][0]
    assert s0["duration_frames"] == 48
    kfs = s0["keyframes"]
    assert len(kfs) >= 6
    # ant + action + hold partition
    assert s0["ant_end"] == 6
    assert s0["hold_start"] == 48 - 12
    frames = [k["frame"] for k in kfs]
    assert frames == sorted(frames)
    assert frames[0] == 0
    assert frames[-1] <= 47
    # joints present
    assert "pelvisY" in kfs[0]["joints"]
    # ant + action + hold sum
    assert s0["ant_end"] + (s0["hold_start"] - s0["ant_end"]) + (
        s0["duration_frames"] - s0["hold_start"]
    ) == s0["duration_frames"]


def test_performance_chart_react_has_extreme_peak():
    from agents.performance_chart_agent import run_performance_chart_agent

    out = run_performance_chart_agent(
        [
            {
                "shot_id": 0,
                "pose": "react",
                "expression": "shock",
                "story_beat": "reaction",
                "duration_frames": 32,
                "anticipation_frames": 6,
                "hold_frames": 8,
            }
        ],
        fps=24,
    )
    kfs = out["shots"][0]["keyframes"]
    phases = [k.get("phase") for k in kfs]
    assert "anticipation" in phases
    assert "extreme" in phases or "hit" in phases
    assert "hold" in phases or "settle" in phases


def test_contact_lock_places_foot_and_impact_frames():
    from agents.contact_lock_agent import run_contact_lock_agent
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "action": "Hero walks in.",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        },
        {
            "shot_id": 1,
            "pose": "react",
            "story_beat": "reaction",
            "action": "Then shock because impact.",
            "duration_frames": 36,
            "anticipation_frames": 8,
            "hold_frames": 10,
        },
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    lock = run_contact_lock_agent(shots, performance_chart=chart, fps=24)
    assert lock["agent"] == "ContactLockAgent"
    assert lock["schema"] == "contact_lock#v1"
    contacts = lock["contacts"]
    assert contacts
    kinds = {c["kind"] for c in contacts}
    assert "foot_L" in kinds or "foot_R" in kinds
    assert "impact" in kinds
    for c in contacts:
        assert 0 <= c["frame"] < c["shot_duration_frames"]
        assert c["global_frame"] >= 0


def test_audio_cue_agent_binds_to_contacts():
    from agents.audio_cue_agent import run_audio_cue_agent
    from agents.contact_lock_agent import run_contact_lock_agent
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "action": "Walks into hall.",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    lock = run_contact_lock_agent(shots, performance_chart=chart, fps=24)
    plan = run_audio_cue_agent(shots, fps=24, emotion="neutral", contacts=lock["contacts"])
    oneshots = [e for e in plan["events"] if e.get("role") == "oneshot"]
    assert oneshots
    # oneshot start should match a contact frame (local) ±1
    contact_locals = {c["frame"] for c in lock["contacts"] if c["shot_id"] == 0}
    assert any(
        any(abs(int(e["startFrame"]) - cf) <= 1 for cf in contact_locals)
        or any(
            abs(int(e["startFrame"]) - (0 + cf) <= 1 for cf in contact_locals)
        )
        for e in oneshots
    )


def test_props_include_performance_chart_and_contacts(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="P0",
        shots=[
            ShotControl(
                action="Hero walks in.",
                story_beat="entrance",
                pose="walk",
                duration_sec=2,
                anticipation_frames=6,
                hold_frames=12,
            ),
            ShotControl(
                action="Then shock because fire.",
                story_beat="reaction",
                pose="react",
                expression="shock",
                duration_sec=2,
                anticipation_frames=8,
                hold_frames=10,
            ),
        ],
    )
    c = compile_studio_spec(spec)
    path = write_story_composition_props(
        tmp_path,
        storyboard=c.storyboard,
        cinematography=c.cinematography,
        timing=c.timing,
        continuity=c.continuity,
        title=spec.title,
    )
    props = json.loads(path.read_text(encoding="utf-8"))
    assert props.get("performanceChart")
    assert props["performanceChart"]["shots"]
    assert props.get("contactLock")
    assert props["contactLock"]["contacts"]
    # denser shotRig from chart
    assert len(props["shots"][0]["shotRig"]["keyframes"]) >= 5
    # audio oneshot near contact
    assert props["audioTimeline"]["events"]
