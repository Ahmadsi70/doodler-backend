"""
FoleyTimelineAgent — anticipation / brake / impact locked to contacts.

Why: AudioCue beds + oneshots are shot-scoped; Foley needs ms-accurate
pre-hit leads separate from ambience beds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from agents.audio_cue_agent import load_audio_catalog
except ImportError:
    from .audio_cue_agent import load_audio_catalog  # type: ignore


def _pick_cue(cues: dict[str, Any], *prefer: str) -> str | None:
    for p in prefer:
        if p in cues and not cues[p].get("alias_of"):
            return p
    for cid, row in cues.items():
        if row.get("role") == "bed" or row.get("alias_of"):
            continue
        tags = {str(t).lower() for t in (row.get("tags") or [])}
        if any(p in tags or p in cid for p in prefer):
            return cid
    return None


def run_foley_timeline_agent(
    shots: list[dict[str, Any]],
    *,
    contacts: list[dict[str, Any]] | None = None,
    fps: int = 24,
) -> dict[str, Any]:
    """
    Emit foley_timeline#v1 events from ContactLock markers.

    Roles: anticipation (−2f), brake (−1f), footstep/impact (0), settle (+2f soft).
    """
    catalog = load_audio_catalog()
    cues = dict(catalog.get("cues") or {})
    foot = _pick_cue(cues, "foley_footstep", "footstep") or _pick_cue(
        cues, "soft", "carpet"
    )
    hit = _pick_cue(cues, "foley_hit", "hit", "punch", "impact")
    soft = _pick_cue(cues, "foley_soft", "soft") or foot

    events: list[dict[str, Any]] = []
    contacts = list(contacts or [])
    for c in contacts:
        gf = int(c.get("global_frame") or 0)
        sid = c.get("shot_id")
        kind = str(c.get("kind") or "")
        if kind.startswith("foot") or kind == "landing":
            main_cue = foot
            main_role = "footstep" if kind.startswith("foot") else "landing"
        else:
            main_cue = hit or soft
            main_role = "impact"

        if not main_cue:
            continue
        row = cues.get(main_cue) or {}
        file_name = Path(str(row.get("file") or "")).name
        file_rel = f"audio/{file_name}" if file_name else None

        # anticipation lead (2 frames ≈ 83ms)
        ant_f = max(0, gf - 2)
        if soft and ant_f < gf:
            srow = cues.get(soft) or row
            events.append(
                {
                    "cue": soft,
                    "file": f"audio/{Path(str(srow.get('file') or '')).name}",
                    "startFrame": ant_f,
                    "shotId": sid,
                    "gainDb": float(srow.get("gain_db") or -16) - 4,
                    "role": "anticipation",
                    "contact_id": c.get("id"),
                    "reason": f"foley_ant:{kind}@{gf}",
                }
            )
        if main_role == "impact" and gf > 0:
            events.append(
                {
                    "cue": main_cue,
                    "file": file_rel,
                    "startFrame": max(0, gf - 1),
                    "shotId": sid,
                    "gainDb": float(row.get("gain_db") or -10) - 2,
                    "role": "brake",
                    "contact_id": c.get("id"),
                    "reason": f"foley_brake:{kind}@{gf}",
                }
            )
        events.append(
            {
                "cue": main_cue,
                "file": file_rel,
                "startFrame": gf,
                "shotId": sid,
                "gainDb": float(row.get("gain_db") or -8),
                "role": main_role,
                "contact_id": c.get("id"),
                "reason": f"foley_lock:{kind}@{gf}",
            }
        )

    # Deduplicate identical start+cue
    seen: set[tuple[Any, ...]] = set()
    uniq: list[dict[str, Any]] = []
    for e in events:
        key = (e.get("startFrame"), e.get("cue"), e.get("role"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)

    return {
        "agent": "FoleyTimelineAgent",
        "schema": "foley_timeline#v1",
        "fps": fps,
        "events": uniq,
        "notes": [f"events={len(uniq)}", f"contacts={len(contacts)}"],
    }


def merge_foley_into_audio_timeline(
    audio_timeline: dict[str, Any],
    foley: dict[str, Any] | None,
) -> dict[str, Any]:
    """Append Foley oneshots into Remotion audioTimeline events."""
    if not foley:
        return audio_timeline
    out = dict(audio_timeline)
    events = list(out.get("events") or [])
    for e in foley.get("events") or []:
        if not e.get("file"):
            continue
        events.append(
            {
                "cue": e.get("cue"),
                "file": e.get("file"),
                "startFrame": int(e.get("startFrame") or 0),
                "durationFrames": None,
                "shotId": e.get("shotId"),
                "gainDb": float(e.get("gainDb") or -10),
                "loop": False,
                "role": e.get("role") or "oneshot",
            }
        )
    out["events"] = events
    return out
