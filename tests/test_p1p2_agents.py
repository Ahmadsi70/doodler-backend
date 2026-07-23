"""P1 TransitionEdge + P2 Foley / Compliance / ActingLead agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_transition_edge_uses_grammar_and_clamps():
    from agents.transition_edge_agent import run_transition_edge_agent

    shots = [
        {"shot_id": 0, "story_beat": "quiet_hold", "duration_frames": 48},
        {"shot_id": 1, "story_beat": "reaction", "duration_frames": 24},
        {"shot_id": 2, "story_beat": "exit", "duration_frames": 36},
    ]
    graph = {
        "edges": [
            {
                "from": 0,
                "to": 1,
                "transition": "hard_cut",
                "risk": "screen_direction_flip",
            },
            {"from": 1, "to": 2, "transition": "crossfade", "risk": None},
        ]
    }
    out = run_transition_edge_agent(shots, continuity_graph=graph, fps=24)
    assert out["agent"] == "TransitionEdgeAgent"
    assert out["schema"] == "transition_edges#v1"
    assert len(out["edges"]) == 2
    e0 = out["edges"][0]
    assert e0["id"] == "hard_cut"
    assert e0["slide"] is False
    assert e0["frames"] <= 8  # clamped for short destination / risk
    assert e0["safe"] is False
    e1 = out["edges"][1]
    assert e1["id"] in {"hard_cut", "crossfade"}  # reaction→* prefers hard_cut
    assert e1["frames"] >= 2


def test_foley_timeline_binds_to_contacts():
    from agents.contact_lock_agent import run_contact_lock_agent
    from agents.foley_timeline_agent import run_foley_timeline_agent
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "walk",
            "story_beat": "entrance",
            "action": "Walks in.",
            "duration_frames": 48,
            "anticipation_frames": 6,
            "hold_frames": 12,
        },
        {
            "shot_id": 1,
            "pose": "react",
            "story_beat": "reaction",
            "action": "Shock impact hit.",
            "duration_frames": 36,
            "anticipation_frames": 8,
            "hold_frames": 10,
        },
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    lock = run_contact_lock_agent(shots, performance_chart=chart, fps=24)
    foley = run_foley_timeline_agent(shots, contacts=lock["contacts"], fps=24)
    assert foley["agent"] == "FoleyTimelineAgent"
    assert foley["schema"] == "foley_timeline#v1"
    roles = {e["role"] for e in foley["events"]}
    assert "footstep" in roles or "impact" in roles
    assert "anticipation" in roles or "brake" in roles
    contact_globals = {c["global_frame"] for c in lock["contacts"]}
    for e in foley["events"]:
        if e["role"] in {"footstep", "impact"}:
            assert e["startFrame"] in contact_globals


def test_compliance_frame_flags_real_checks():
    from agents.compliance_frame_agent import run_compliance_frame_agent

    props = {
        "fps": 24,
        "continuity": {
            "lineSide": "left",
            "approved": True,
            "violations": [],
            "graph": {
                "nodes": [
                    {"shot_id": 0, "eyeline": "consistent", "screen_direction": "L_to_R"},
                    {"shot_id": 1, "eyeline": "consistent", "screen_direction": "L_to_R"},
                ],
                "edges": [{"from": 0, "to": 1, "risk": None}],
                "violations": [],
            },
        },
        "performanceChart": {
            "fps": 24,
            "shots": [{"shot_id": 0, "duration_frames": 24, "keyframes": [{}, {}, {}, {}]}],
        },
        "contactLock": {"contacts": [{"shot_id": 0, "kind": "foot_L"}]},
    }
    out = run_compliance_frame_agent(props)
    assert out["agent"] == "ComplianceFrameAgent"
    assert out["schema"] == "compliance_frame#v1"
    assert out["flags"]["fps_ok"] is True
    assert out["flags"]["line_180_ok"] is True
    assert out["flags"]["eyeline_ok"] is True
    assert out["flags"]["chart_present"] is True
    assert out["passed"] is True

    bad = dict(props)
    bad["fps"] = 30
    bad["continuity"] = {
        "approved": False,
        "violations": ["180 crossed"],
        "graph": {
            "nodes": [
                {"shot_id": 0, "eyeline": "mismatch"},
                {"shot_id": 1, "eyeline": "consistent"},
            ],
            "edges": [{"from": 0, "to": 1, "risk": "screen_direction_flip"}],
            "violations": ["flip"],
        },
    }
    bad_out = run_compliance_frame_agent(bad)
    assert bad_out["passed"] is False
    assert bad_out["flags"]["fps_ok"] is False
    assert bad_out["flags"]["line_180_ok"] is False
    assert bad_out["flags"]["eyeline_ok"] is False


def test_acting_lead_eyes_before_head():
    from agents.acting_lead_agent import (
        apply_acting_lead_to_chart,
        run_acting_lead_agent,
    )
    from agents.performance_chart_agent import run_performance_chart_agent

    shots = [
        {
            "shot_id": 0,
            "pose": "react",
            "expression": "shock",
            "story_beat": "reaction",
            "duration_frames": 32,
            "anticipation_frames": 6,
            "hold_frames": 8,
        }
    ]
    chart = run_performance_chart_agent(shots, fps=24)
    lead = run_acting_lead_agent(shots, performance_chart=chart, fps=24)
    assert lead["agent"] == "ActingLeadAgent"
    assert lead["schema"] == "acting_lead#v1"
    assert lead["shots"]
    s0 = lead["shots"][0]
    assert 2 <= s0["eyes_lead_frames"] <= 4
    assert s0["eyes_frame"] < s0["head_frame"]
    enriched = apply_acting_lead_to_chart(chart, lead)
    assert enriched["shots"][0].get("expression_curve")
    ec = enriched["shots"][0]["expression_curve"]
    assert len(ec) >= 2
    assert ec[0]["frame"] <= s0["eyes_frame"]


def test_props_include_p1p2_artifacts(tmp_path: Path):
    from studio_spec import ShotControl, StudioSpec
    from tools.remotion_emitter import write_story_composition_props
    from tools.studio_api import compile_studio_spec

    spec = StudioSpec(
        title="P1P2",
        shots=[
            ShotControl(
                action="Hero walks in quietly.",
                story_beat="quiet_hold",
                pose="walk",
                duration_sec=2,
            ),
            ShotControl(
                action="Then shock because fire impact.",
                story_beat="reaction",
                pose="react",
                expression="shock",
                camera="motivated_push",
                duration_sec=2,
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
    assert props.get("transitionEdges")
    assert props["transitionEdges"]["edges"]
    assert props["shots"][1].get("transitionIn", {}).get("id")
    assert props.get("foleyTimeline")
    assert props["foleyTimeline"]["events"]
    assert props.get("complianceFrame")
    assert "fps_ok" in props["complianceFrame"]["flags"]
    assert props.get("actingLead")
    assert props["shots"][1].get("expressionCurve") or props["actingLead"]["shots"]
