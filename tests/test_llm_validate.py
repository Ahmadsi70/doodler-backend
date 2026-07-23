"""LLM schema validators reject garbage before merge."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_validate_storyboard_rejects_empty_action():
    from agents.llm_enrich import validate_storyboard_shots

    assert validate_storyboard_shots([{"shot_id": 0, "action": "", "duration_sec": 3}]) is None
    ok = validate_storyboard_shots(
        [{"shot_id": 0, "title": "A", "action": "Enters", "duration_sec": 3}]
    )
    assert ok and ok[0]["action"] == "Enters"


def test_validate_timing_enforces_floors():
    from agents.llm_enrich import validate_timing_shots

    rows = validate_timing_shots(
        [{"shot_id": 0, "duration_sec": 2, "hold_frames": 1, "anticipation_frames": 1}]
    )
    assert rows
    assert rows[0]["hold_frames"] >= 8
    assert rows[0]["anticipation_frames"] >= 4


def test_williams_paths_status_shape():
    from tools.williams_paths import williams_status

    st = williams_status()
    assert "ready" in st and "hint" in st
