"""Unified craft path: Director Board uses same supervised graph as CLI (no export)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIEF = (
    "Hero enters the archive.\n\n"
    "Then they react in shock because the letter burns.\n\n"
    "They leave into rain."
)


def test_brief_craft_graph_stops_before_export(tmp_path: Path):
    from tools.studio_graph import run_brief_craft_graph

    out = run_brief_craft_graph(
        BRIEF,
        tmp_path / "craft_job",
        extras={
            "runtime_seconds": 24,
            "use_llm": False,
            "quality": "light",
            "skip_screenplay_gate": True,
        },
        max_revision_passes=1,
    )
    assert out.get("phase") == "craft_complete"
    assert out.get("chain", {}).get("storyboard", {}).get("shots")
    assert (tmp_path / "craft_job" / "checkpoints" / "brief_craft_graph.json").is_file()
    assert (tmp_path / "craft_job" / "agents" / "draft_screenplay.json").is_file()
    export_md = tmp_path / "craft_job" / "export" / "screenplay.md"
    assert not export_md.is_file()


def test_design_from_brief_uses_craft_graph(tmp_path: Path):
    from tools.director_board import design_from_brief

    phases: list[str] = []
    board = design_from_brief(
        BRIEF,
        job_dir=tmp_path,
        runtime_seconds=24,
        use_llm=False,
        on_phase=phases.append,
    )
    assert len(board.spec.shots) >= 3
    assert (tmp_path / "checkpoints" / "brief_craft_graph.json").is_file()
    assert (tmp_path / "design" / "craft_meta.json").is_file()
    meta = json.loads(
        (tmp_path / "design" / "craft_meta.json").read_text(encoding="utf-8")
    )
    assert meta.get("graph") == "brief_craft"
    assert "supervisor" in meta
    assert phases, "on_phase should receive craft progress"
