"""Golden contract: Spec → story_props v3 fields Remotion consumes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "fixtures" / "golden" / "story_props_contract" / "story_props.json"

REQUIRED_SHOT_KEYS = {
    "shotRig",
    "envProfile",
    "craftHints",
    "captionMode",
    "cameraMove",
    "transitionIn",
}


def test_golden_props_contract_file_exists():
    assert GOLDEN.is_file(), f"missing {GOLDEN}"


def test_golden_props_contract_shape():
    props = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert props["visualVersion"] >= 3
    assert isinstance(props.get("continuity", {}).get("graph"), dict)
    assert props["shots"]
    for shot in props["shots"]:
        missing = REQUIRED_SHOT_KEYS - set(shot)
        assert not missing, f"shot missing {missing}"
