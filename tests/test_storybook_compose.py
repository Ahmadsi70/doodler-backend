"""TDD: storybook compose is Ken Burns + crossfade — no cutout layers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from agents.storybook_page_agent import plan_storybook
from libraries.storybook_pipeline import render_storybook


def test_render_storybook_mock_writes_mp4(tmp_path: Path) -> None:
    plan = plan_storybook(
        "A fox finds a lantern. Mist rises by the bridge.",
        title="Lantern Fox",
        target_sec=4.0,
        language="en",
        crossfade_sec=0.25,
    )
    # Inject painted page stills (no live Gemini).
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    still_paths: list[Path] = []
    for i, page in enumerate(plan.pages):
        arr = np.zeros((180, 320, 3), dtype=np.uint8)
        arr[:, :] = (40 + i * 40, 80, 120)
        path = pages_dir / f"page_{i:02d}.png"
        Image.fromarray(arr).save(path)
        still_paths.append(path)

    report = render_storybook(
        plan,
        tmp_path / "out",
        still_paths=still_paths,
        width=320,
        height=180,
        fps=12,
        mock=True,
    )
    assert report["ok"] is True
    assert report["engine"] == "storybook"
    final = Path(report["final_mp4"])
    assert final.is_file()
    assert final.stat().st_size > 1000
    assert "cutout" not in report
    assert report["n_pages"] == len(plan.pages)
