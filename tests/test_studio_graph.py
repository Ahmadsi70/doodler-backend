"""LangGraph studio orchestrator tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_spec import ShotControl, StudioSpec


def _mini_spec() -> StudioSpec:
    return StudioSpec(
        title="گراف",
        shots=[
            ShotControl(
                title="یک",
                action="شخص وارد می‌شود.",
                duration_sec=3,
                story_beat="entrance",
            )
        ],
    )


def test_langgraph_available():
    from tools.studio_graph import langgraph_available

    assert langgraph_available() is True


def test_brief_studio_graph_export(tmp_path):
    from tools.studio_graph import run_brief_studio_graph

    brief = "ورود.\n\nواکنش.\n\nخروج."
    out = run_brief_studio_graph(
        brief,
        tmp_path / "job1",
        extras={"quality": "light", "runtime_seconds": 12},
        max_revision_passes=1,
    )
    assert out.get("phase") in {"gate_pass", "exported", "gate_fail"}
    assert (tmp_path / "job1" / "checkpoints" / "brief_graph.json").is_file()
    export_root = tmp_path / "job1" / "export"
    assert export_root.is_dir()
    assert (export_root / "screenplay.md").is_file()
    assert (export_root / "prompts" / "shot_00_motion.txt").is_file()


def test_spec_export_graph(tmp_path):
    from tools.studio_graph import run_spec_export_graph

    spec = _mini_spec()
    out = run_spec_export_graph(
        spec.to_public_dict(),
        tmp_path / "job2",
        approved=True,
        targets=["prompts"],
    )
    assert out.get("ok") is True
    gate = json.loads((tmp_path / "job2" / "export" / "export_gate.json").read_text(encoding="utf-8"))
    assert gate["ok"] is True
    assert (tmp_path / "job2" / "checkpoints" / "export_graph.json").is_file()


def test_spec_export_parks_at_await_approve(tmp_path):
    from tools.studio_graph import park_spec_export_graph, resume_spec_export_graph

    spec = _mini_spec()
    parked = park_spec_export_graph(
        spec.to_public_dict(),
        tmp_path / "job4",
        targets=["prompts"],
    )
    assert parked.get("awaiting_approve") is True

    out = resume_spec_export_graph(
        tmp_path / "job4",
        approved=True,
        spec_dict=spec.to_public_dict(),
        targets=["prompts"],
    )
    assert out.get("ok") is True
    assert out.get("phase") == "gate_pass"


def test_spec_export_blocked_without_approve(tmp_path):
    from tools.studio_graph import park_spec_export_graph, resume_spec_export_graph

    spec = _mini_spec()
    park_spec_export_graph(spec.to_public_dict(), tmp_path / "job3", targets=["prompts"])
    out = resume_spec_export_graph(
        tmp_path / "job3",
        approved=False,
        spec_dict=spec.to_public_dict(),
    )
    assert out.get("ok") is False
    assert "approved" in (out.get("error") or "").lower()


def test_supervisor_route_to_revise():
    from tools.studio_graph import _route_after_supervisor

    assert _route_after_supervisor({"supervisor": {"passed": True}}) == "export"
    assert (
        _route_after_supervisor(
            {
                "supervisor": {"passed": False, "revision_target": "StoryboardAgent"},
                "revision_passes": 0,
                "max_revision_passes": 2,
            }
        )
        == "revise"
    )
