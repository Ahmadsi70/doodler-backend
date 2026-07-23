"""P1 — screenplay human gate before storyboard craft."""

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


def test_park_craft_pauses_at_screenplay(tmp_path: Path):
    from tools.studio_graph import has_screenplay_interrupt, park_craft_for_screenplay

    out = park_craft_for_screenplay(
        BRIEF,
        tmp_path / "park_job",
        extras={"runtime_seconds": 24, "use_llm": False, "quality": "light"},
    )
    assert has_screenplay_interrupt(out)
    assert out.get("phase") == "await_screenplay"
    assert (tmp_path / "park_job" / "agents" / "draft_screenplay.json").is_file()
    assert (tmp_path / "park_job" / "design" / "screenplay_draft.json").is_file()
    chain = out.get("chain") or {}
    assert not (chain.get("storyboard") or {}).get("shots")


def test_resume_craft_after_screenplay_approval(tmp_path: Path):
    from tools.director_board import finish_design_after_screenplay, park_design_for_screenplay

    job = tmp_path / "resume_job"
    park_design_for_screenplay(
        BRIEF,
        job_dir=job,
        runtime_seconds=24,
        use_llm=False,
    )
    draft = json.loads(
        (job / "design" / "screenplay_draft.json").read_text(encoding="utf-8")
    )
    edited_md = (draft.get("screenplay_md") or "") + "\n\n<!-- approved -->"
    board = finish_design_after_screenplay(
        BRIEF,
        job_dir=job,
        screenplay_md=edited_md,
        runtime_seconds=24,
        use_llm=False,
    )
    assert len(board.spec.shots) >= 3
    assert (job / "agents" / "draft_screenplay.json").is_file()
    saved = json.loads(
        (job / "agents" / "draft_screenplay.json").read_text(encoding="utf-8")
    )
    assert "<!-- approved -->" in str(saved.get("screenplay_md") or "")


def test_skip_screenplay_gate_one_shot(tmp_path: Path):
    from tools.studio_graph import run_brief_craft_graph

    out = run_brief_craft_graph(
        BRIEF,
        tmp_path / "skip_job",
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
