from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.style_catalog import _starter_pack, clear_style_cache, default_style_id


@pytest.fixture(autouse=True)
def _clear():
    clear_style_cache()
    yield
    clear_style_cache()


def test_styles_story_only():
    for row in _starter_pack().get("styles") or []:
        assert (row.get("studio_fit") or []) == ["studio_story"]


def test_default_style():
    assert default_style_id() == "symmetrical_pastel_cinema"
