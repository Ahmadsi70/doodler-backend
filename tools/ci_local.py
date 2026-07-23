"""
Local CI plan — mirror GitHub Actions without requiring `gh`.

Why: Story may not have GitHub CLI installed; operators still need a green checklist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def ci_local_plan(root: Path | str | None = None) -> dict[str, Any]:
    r = Path(root or Path(__file__).resolve().parents[1])
    return {
        "root": str(r.resolve()),
        "workflow": str(r / ".github" / "workflows" / "ci.yml"),
        "steps": [
            {
                "id": "pytest",
                "cmd": 'python -m pytest tests -q --tb=short',
                "env": {
                    "ANIMATION_DETERMINISTIC_SLIDES": "1",
                    "STORY_USE_LLM": "0",
                    "QUALITY_GATE_STRICT": "0",
                },
            },
            {
                "id": "smoke_light",
                "cmd": "python scripts/smoke_render.py",
                "env": {
                    "ANIMATION_DETERMINISTIC_SLIDES": "1",
                    "STORY_USE_LLM": "0",
                },
            },
            {
                "id": "golden_pro_props",
                "cmd": "python -m pytest tests/test_story_pro_golden.py -q --tb=short",
                "env": {"STORY_USE_LLM": "0"},
            },
        ],
        "github_doc": str(r / "docs" / "GITHUB.md"),
    }
