"""
Style → executable runtime bindings for Story.

Maps ``style_profile`` / resolved catalog styles to:
  - Camera/framing specs consumed by Remotion props
  - Optional FFmpeg ``eq`` / ``colorbalance`` grade chains (Light draft)

Story Pro grades in Remotion via palette; Light may ignore VF chains.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# FFmpeg grade chains — professional, asset-free (no external .cube LUT required).
# Order: tonal eq → optional colorbalance / hue.
GRADE_VF: dict[str, str] = {
    "pastel_muted": (
        "eq=saturation=0.75:contrast=0.90:gamma=1.05,"
        "colorbalance=rs=0.04:gs=0.02:bs=-0.02:rm=0.03:gm=0.01"
    ),
    "moody_teal_orange": (
        "eq=saturation=0.95:contrast=1.15:gamma=0.98,"
        "colorbalance=bs=0.08:gs=-0.02:rs=-0.03:rh=0.10:bh=-0.06:gh=-0.02"
    ),
    "vivid_pop": "eq=saturation=1.25:contrast=1.10:brightness=0.02:gamma=1.0",
    "bw_graphic": "hue=s=0,eq=contrast=1.30:gamma=0.95:brightness=0.01",
    "clean_corporate": (
        "eq=saturation=0.85:contrast=1.00:gamma=1.02,"
        "colorbalance=bs=0.03:rs=-0.01"
    ),
}

# Camera override specs consumed by Blender (no bpy import here — portable).
CAMERA_SPECS: dict[str, dict[str, Any]] = {
    "locked_symmetric": {
        "mode": "static",
        "location": [0.0, -7.5, 2.8],
        "look_at": [0.0, 0.0, 1.0],
        "fov_deg": 40.0,
        "dutch_deg": 0.0,
    },
    "motivated_track": {
        "mode": "track",
        "keyframes": [
            {
                "t": 0.0,
                "location": [-1.2, -8.0, 2.6],
                "look_at": [0.0, 0.0, 1.0],
            },
            {
                "t": 1.0,
                "location": [1.2, -7.2, 2.9],
                "look_at": [0.0, 0.0, 1.05],
            },
        ],
        "fov_deg": 42.0,
    },
    "documentary_hand": {
        "mode": "hand",
        "keyframes": [
            {
                "t": 0.0,
                "location": [0.0, -7.8, 2.7],
                "look_at": [0.0, 0.0, 1.0],
            },
            {
                "t": 0.45,
                "location": [0.08, -7.85, 2.72],
                "look_at": [0.02, 0.0, 1.0],
            },
            {
                "t": 1.0,
                "location": [-0.06, -7.75, 2.68],
                "look_at": [-0.01, 0.0, 0.98],
            },
        ],
        "fov_deg": 45.0,
    },
    "kinetic_push": {
        "mode": "push",
        "keyframes": [
            {
                "t": 0.0,
                "location": [0.0, -10.0, 3.2],
                "look_at": [0.0, 0.0, 1.0],
            },
            {
                "t": 0.28,
                "location": [0.0, -6.0, 2.4],
                "look_at": [0.0, 0.0, 1.0],
            },
            {
                "t": 1.0,
                "location": [0.0, -6.0, 2.4],
                "look_at": [0.0, 0.0, 1.0],
            },
        ],
        "fov_deg": 38.0,
    },
    "ar_orbit_safe": {
        "mode": "static",
        "location": [2.8, -4.5, 2.2],
        "look_at": [0.0, 0.0, 0.8],
        "fov_deg": 35.0,
        "dutch_deg": 0.0,
    },
}


def load_style_profile(job_dir: Path | str | None) -> dict[str, Any] | None:
    """Load ``style_profile.json`` from a job workspace if present."""
    if not job_dir:
        return None
    path = Path(job_dir) / "style_profile.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def grade_vf_for(
    grade_preset: str | None = None,
    *,
    resolved: dict[str, Any] | None = None,
) -> str | None:
    """Return FFmpeg ``-vf`` / filtergraph fragment for a grade preset."""
    key = grade_preset or (resolved or {}).get("grade_preset")
    if not key:
        return None
    return GRADE_VF.get(str(key))


def camera_spec_for(
    camera_preset: str | None = None,
    *,
    resolved: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return Blender camera override spec for a camera preset."""
    key = camera_preset or (resolved or {}).get("camera_preset")
    if not key:
        return None
    spec = CAMERA_SPECS.get(str(key))
    return dict(spec) if spec else None


def runtime_bundle_from_resolved(resolved: dict[str, Any] | None) -> dict[str, Any]:
    """Compact bundle for logs / style_profile enrichment."""
    resolved = resolved or {}
    cam_key = resolved.get("camera_preset")
    grade_key = resolved.get("grade_preset")
    return {
        "style_id": resolved.get("style_id"),
        "camera_preset": cam_key,
        "grade_preset": grade_key,
        "camera_spec": camera_spec_for(cam_key),
        "grade_vf": grade_vf_for(grade_key),
        "pace_preset": resolved.get("pace_preset"),
        "motion_style": resolved.get("motion_style"),
        "endcard_preset": resolved.get("endcard_preset"),
    }


def enrich_style_profile_file(job_dir: Path | str, resolved: dict[str, Any]) -> Path:
    """
    Rewrite ``style_profile.json`` with executable ``camera_spec`` + ``grade_vf``.

    Safe to call after ``write_style_profile``.
    """
    out = Path(job_dir) / "style_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle = runtime_bundle_from_resolved(resolved)
    payload = dict(resolved)
    payload.update(
        {
            "camera_spec": bundle.get("camera_spec"),
            "grade_vf": bundle.get("grade_vf"),
            "runtime_stage": 1,
        }
    )
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
