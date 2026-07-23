"""One-shot importer: Downloads Williams JSON → libraries/williams (fixed)."""

from __future__ import annotations

import json
import re
from pathlib import Path

SRC = Path(r"C:\Users\badri\Downloads")
DST = Path(__file__).resolve().parents[1] / "libraries" / "williams"
TIMING_RULES = Path(__file__).resolve().parents[1] / "libraries" / "story" / "timing_rules.json"


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)

    principles = json.loads((SRC / "principles.json").read_text(encoding="utf-8"))
    (DST / "principles.json").write_text(
        json.dumps({"principles": principles}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    shots = json.loads((SRC / "shot_behaviors.json").read_text(encoding="utf-8"))
    (DST / "shot_behaviors.json").write_text(
        json.dumps({"shot_behaviors": shots}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    ap = json.loads((SRC / "anti_patterns.json").read_text(encoding="utf-8"))
    for row in ap.get("anti_patterns", []):
        for key in ("symptom", "why_bad", "fix"):
            val = row.get(key)
            if isinstance(val, str):
                row[key] = re.sub(r"\s*\[[0-9]+\]", "", val).strip()
    (DST / "anti_patterns.json").write_text(
        json.dumps(ap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    text = (SRC / "timing_recipes.json").read_text(encoding="utf-8")
    text = re.sub(r'"or_range":\s+(?=})', '"or_range": null ', text)
    recipes_doc = json.loads(text)

    timing_rules = json.loads(TIMING_RULES.read_text(encoding="utf-8"))
    phys = timing_rules["physics"]
    act = timing_rules["acting_mechanics"]
    fill = {
        "heavy_lift_anticipation": {
            "anticipation_frames": phys["heavy_weight_anticipation_frames"],
            "hold_frames": act["minimum_moving_hold_frames"],
            "duration_frames_hint": phys["heavy_weight_anticipation_frames"]
            + phys["cushion_settle_frames"],
            "phases": [
                {
                    "name": "anticipation",
                    "frames": phys["heavy_weight_anticipation_frames"],
                    "or_range": None,
                }
            ],
        },
        "light_flick": {
            "anticipation_frames": phys["light_weight_anticipation_frames"],
            "hold_frames": 0,
            "duration_frames_hint": phys["fast_action_frames"][1],
            "phases": [
                {
                    "name": "action",
                    "frames": phys["fast_action_frames"][1],
                    "or_range": phys["fast_action_frames"],
                }
            ],
        },
        "standard_blink": {
            "anticipation_frames": 0,
            "hold_frames": 0,
            "duration_frames_hint": act["blink_duration_frames"],
            "phases": [
                {
                    "name": "action",
                    "frames": act["blink_duration_frames"],
                    "or_range": None,
                }
            ],
        },
        "eye_dart": {
            "anticipation_frames": 0,
            "hold_frames": 0,
            "duration_frames_hint": act["eye_dart_frames"],
            "phases": [
                {
                    "name": "action",
                    "frames": act["eye_dart_frames"],
                    "or_range": None,
                }
            ],
        },
        "head_turn_delay": {
            "anticipation_frames": 0,
            "hold_frames": act["head_turn_delay_frames"],
            "duration_frames_hint": act["head_turn_delay_frames"],
            "phases": [
                {
                    "name": "hold",
                    "frames": act["head_turn_delay_frames"],
                    "or_range": None,
                }
            ],
        },
        "moving_hold": {
            "anticipation_frames": 0,
            "hold_frames": act["minimum_moving_hold_frames"],
            "duration_frames_hint": act["preferred_moving_hold_range_frames"][1],
            "phases": [
                {
                    "name": "hold",
                    "frames": act["minimum_moving_hold_frames"],
                    "or_range": act["preferred_moving_hold_range_frames"],
                }
            ],
        },
        "follow_through_settle": {
            "anticipation_frames": 0,
            "hold_frames": phys["follow_through_settle_frames"][1],
            "duration_frames_hint": phys["follow_through_settle_frames"][1],
            "phases": [
                {
                    "name": "settle",
                    "frames": phys["follow_through_settle_frames"][0],
                    "or_range": phys["follow_through_settle_frames"],
                }
            ],
        },
    }

    for recipe in recipes_doc["recipes"]:
        for phase in recipe.get("phases") or []:
            if phase.get("or_range") == "" or "or_range" not in phase:
                phase["or_range"] = None
        rid = recipe["id"]
        if rid in fill and float(recipe.get("confidence") or 0) < 0.6:
            filled = fill[rid]
            recipe["maps_to_project_fields"] = {
                "anticipation_frames": filled["anticipation_frames"],
                "hold_frames": filled["hold_frames"],
                "duration_frames_hint": filled["duration_frames_hint"],
            }
            recipe["phases"] = filled["phases"]
            recipe["backfilled_from"] = "libraries/story/timing_rules.json"
            note = recipe.get("notes") or ""
            if "[backfilled" not in note:
                recipe["notes"] = (note + " [backfilled from project timing_rules]").strip()

    (DST / "timing_recipes.json").write_text(
        json.dumps(recipes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    meta = {
        "id": "williams_craft_pack",
        "version": "1.0.0",
        "fps": 24,
        "source_book": "The Animator's Survival Kit (Richard Williams)",
        "provenance": "NotebookLM operational distill — not verbatim book text",
        "files": [
            "principles.json",
            "timing_recipes.json",
            "shot_behaviors.json",
            "anti_patterns.json",
        ],
    }
    (DST / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for path in sorted(DST.glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
        print("ok", path.name)


if __name__ == "__main__":
    main()
