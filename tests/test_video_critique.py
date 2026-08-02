"""TDD: Gemini video critique report for produced Story MP4s."""

from __future__ import annotations

import json
from pathlib import Path

from libraries.video_critique import (
    CRITIQUE_SCHEMA,
    VideoCritiqueReport,
    analyze_story_video,
    critique_prompt,
    parse_critique_json,
)


def test_critique_prompt_mentions_storybook_checks() -> None:
    p = critique_prompt(story="A fox walks with a lantern.")
    assert "weakness" in p.lower() or "ضعف" in p
    assert "timestamp" in p.lower() or "mm:ss" in p.lower()
    assert "storybook" in p.lower() or "ken burns" in p.lower()


def test_parse_critique_json_tolerates_fences() -> None:
    raw = """```json
    {
      "overall_score": 6,
      "summary": "ok",
      "strengths": ["style"],
      "weaknesses": [
        {"timestamp": "00:12", "category": "composite", "severity": "rect seam", "severity": "fix matte"}
      ],
      "fix_plan": ["tighten cutouts"]
    }
    ```"""
    data = parse_critique_json(raw)
    assert data["overall_score"] == 6
    assert data["weaknesses"][0]["category"] == "composite"


def test_analyze_story_video_mock_writes_report(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"not-a-real-mp4")
    report = analyze_story_video(
        video,
        story="Fox finds a lantern.",
        mock=True,
        output_dir=tmp_path,
    )
    assert isinstance(report, VideoCritiqueReport)
    assert report.schema_version == CRITIQUE_SCHEMA
    assert report.ok
    assert report.report_json is not None and report.report_json.is_file()
    payload = json.loads(report.report_json.read_text(encoding="utf-8"))
    assert payload["video_path"].endswith("final.mp4")
    assert "weaknesses" in payload
