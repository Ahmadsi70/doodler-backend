"""P1: LocomotionCycleAgent + CameraCurveAgent + Supervisor frame gate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_locomotion_cycle_emits_four_beats():
    from agents.locomotion_cycle_agent import run_locomotion_cycle_agent
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    loco = run_locomotion_cycle_agent(shots, performance_chart=chart, fps=24)
    assert loco["agent"] == "LocomotionCycleAgent"
    assert loco["schema"] == "locomotion_cycle#v1"
    assert len(loco["cycles"]) == 1
    c0 = loco["cycles"][0]
    assert c0["gait"] == "walk"
    assert c0["cycle_frames"] == 24
    phases = [b["phase"] for b in c0["beats"]]
    for need in ("contact", "down", "passing", "up"):
        assert need in phases
    # beats inside action window
    for b in c0["beats"]:
        assert 6 <= b["frame"] < 48 - 12


def test_locomotion_enriches_chart_phases():
    from agents.locomotion_cycle_agent import (
        apply_locomotion_to_chart,
        run_locomotion_cycle_agent,
    )
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    loco = run_locomotion_cycle_agent(shots, performance_chart=chart, fps=24)
    enriched = apply_locomotion_to_chart(chart, loco)
    phases = {k.get("phase") for k in enriched["shots"][0]["keyframes"]}
    assert {"contact", "down", "passing", "up"} <= phases


def test_camera_curve_push_has_ease_keyframes():
    from agents.camera_curve_agent import run_camera_curve_agent

    shots = [
        {
            "shot_id": 0,
            "story_beat": "reaction",
            "camera": "motivated_push",
            "camera_move": {"id": "motivated_push", "scale_end": 1.14, "translate_x": 0},
            "duration_frames": 36,
            "anticipation_frames": 8,
            "hold_frames": 10,
        },
        {
            "shot_id": 1,
            "story_beat": "entrance",
            "camera": "pan_follow",
            "camera_move": {"id": "pan_follow", "scale_end": 1.0, "translate_x": 40},
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        },
    ]
    out = run_camera_curve_agent(shots, fps=24)
    assert out["agent"] == "CameraCurveAgent"
    assert out["schema"] == "camera_curve#v1"
    assert len(out["shots"]) == 2
    push = out["shots"][0]
    assert push["move_id"] == "motivated_push"
    kfs = push["keyframes"]
    assert len(kfs) >= 3
    assert kfs[0]["frame"] == 0
    assert kfs[0]["scale"] == 1.0
    assert kfs[-1]["scale"] >= 1.1
    assert any(k.get("ease") == "ease_in_out" for k in kfs)
    pan = out["shots"][1]
    assert pan["keyframes"][-1]["tx"] != 0


def test_frame_gate_fails_sparse_chart():
    from tools.frame_gate import run_frame_gate

    sparse = {
        "performanceChart": {
            "shots": [
                {
                    "shot_id": 0,
                    "pose": "walk",
                    "duration_frames": 48,
                    "keyframes": [{"frame": 0, "phase": "start", "joints": {}}],
                }
            ]
        },
        "contactLock": {"contacts": []},
    }
    report = run_frame_gate(sparse, strict=False)
    assert report["passed"] is False
    assert any("sparse" in f or "keyframe" in f for f in report["findings"])


def test_frame_gate_passes_dense_chart_with_contacts():
    from agents.contact_lock_agent import run_contact_lock_agent
    from agents.locomotion_cycle_agent import (
        apply_locomotion_to_chart,
        run_locomotion_cycle_agent,
    )
    from agents.performance_chart_agent import run_performance_chart_agent
    from tools.frame_gate import run_frame_gate

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "action": "Hero walks in.",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    loco = run_locomotion_cycle_agent(shots, performance_chart=chart, fps=24)
    chart = apply_locomotion_to_chart(chart, loco)
    lock = run_contact_lock_agent(shots, performance_chart=chart, fps=24)
    report = run_frame_gate(
        {"performanceChart": chart, "contactLock": lock, "locomotionCycles": loco},
        strict=False,
    )
    assert report["passed"] is True


def test_frame_gate_strict_raises():
    from tools.frame_gate import run_frame_gate

    sparse = {
        "performanceChart": {
            "shots": [
                {
                    "shot_id": 0,
                    "pose": "idle",
                    "duration_frames": 24,
                    "keyframes": [{"frame": 0, "joints": {}}],
                }
            ]
        }
    }
    old = os.environ.get("FRAME_GATE_STRICT")
    os.environ["FRAME_GATE_STRICT"] = "1"
    try:
        raised = False
        try:
            run_frame_gate(sparse, strict=True)
        except RuntimeError:
            raised = True
        assert raised
    finally:
        if old is None:
            os.environ.pop("FRAME_GATE_STRICT", None)
        else:
            os.environ["FRAME_GATE_STRICT"] = old


def test_props_include_locomotion_and_camera_curve(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="P1",
        shots=[
            ShotControl(
                action="Hero walks in.",
                story_beat="entrance",
                pose="walk",
                camera="pan_follow",
                duration_sec=2,
                anticipation_frames=6,
                hold_frames=12,
            ),
            ShotControl(
                action="Then shock.",
                story_beat="reaction",
                pose="react",
                expression="shock",
                camera="motivated_push",
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
    assert props.get("locomotionCycles")
    assert props["locomotionCycles"]["cycles"]
    assert props.get("cameraCurves")
    assert props["cameraCurves"]["shots"]
    # shot-level curve attached
    assert props["shots"][0].get("cameraCurve")
    assert len(props["shots"][0]["cameraCurve"]["keyframes"]) >= 2
    # walk chart has four-beat phases
    walk_phases = {
        k.get("phase") for k in props["shots"][0]["shotRig"]["keyframes"]
    }
    assert {"contact", "down", "passing", "up"} & walk_phases
