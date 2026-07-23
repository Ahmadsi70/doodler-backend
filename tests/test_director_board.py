"""Director Board: design preview → revise patch → approve → render gate."""

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


def test_design_from_brief_stops_before_render(tmp_path):
    from tools.director_board import design_from_brief

    board = design_from_brief(
        BRIEF,
        job_dir=tmp_path,
        quality="light",
        runtime_seconds=24,
        use_llm=False,
    )
    assert board.status == "preview"
    assert board.approved is False
    assert len(board.spec.shots) >= 3
    assert (tmp_path / "studio_spec.json").is_file()
    assert (tmp_path / "design" / "director_board.json").is_file()
    assert (tmp_path / "design" / "design_preview.md").is_file()
    assert not (tmp_path / "render.mp4").is_file()


def test_revise_prompt_patches_selected_shots_respects_locks(tmp_path):
    from tools.director_board import design_from_brief, revise_design

    board = design_from_brief(BRIEF, job_dir=tmp_path, runtime_seconds=24)
    # Lock shot 0 completely
    cam0_before = board.spec.shots[0].camera
    pose0_before = board.spec.shots[0].pose
    board = revise_design(
        board,
        revise_prompt="shot 2 make camera static and pose idle",
        shot_indices=[1],
        locked_fields={0: {"camera", "pose", "action"}},
        job_dir=tmp_path,
    )
    assert board.revision_count >= 1
    assert board.spec.shots[0].camera == cam0_before
    assert board.spec.shots[0].pose == pose0_before
    assert board.spec.shots[1].camera == "static"
    assert board.spec.shots[1].pose == "idle"
    hist = json.loads((tmp_path / "design" / "revise_history.json").read_text(encoding="utf-8"))
    assert hist["revisions"]


def test_approve_required_for_render(tmp_path, monkeypatch):
    from tools.director_board import approve_design, design_from_brief, render_approved_design

    monkeypatch.setenv("ANIMATION_OUT_ROOT", str(tmp_path / "out"))
    board = design_from_brief(BRIEF, job_dir=tmp_path / "job", runtime_seconds=18)
    blocked = render_approved_design(board, job_dir=tmp_path / "job")
    assert blocked.get("ok") is False
    assert "not approved" in str(blocked.get("error") or "").lower()

    board = approve_design(board, job_dir=tmp_path / "job")
    assert board.approved is True
    assert board.status == "approved"
    result = render_approved_design(board, job_dir=tmp_path / "job")
    assert result.get("ok") is True
    assert result.get("control_plane") == "studio_spec"


def test_export_design_download_bundle(tmp_path):
    from tools.director_board import design_from_brief, export_design_bundle

    board = design_from_brief(BRIEF, job_dir=tmp_path, runtime_seconds=20)
    bundle = export_design_bundle(board, tmp_path / "download_bundle")
    assert (bundle / "studio_spec.json").is_file()
    assert (bundle / "design_preview.md").is_file()
    assert (bundle / "director_board.json").is_file()
