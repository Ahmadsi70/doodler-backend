"""
AudioCueAgent — pick SFX from the project catalog only.

Why: free-form LLM filenames hallucinate; constrained cue_ids keep Remotion
deterministic and license-safe (Kenney CC0 + procedural beds).
"""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_CATALOG = _ROOT / "libraries" / "audio" / "catalog.json"

_ACTION_TAGS = (
    (re.compile(r"\b(walk|enter|step|foot|hall|corridor)\b", re.I), ["footstep", "walk"]),
    (re.compile(r"(وارد|قدم|گام|راه می‌رود|راه ميرود|قدم می‌زند)", re.I), ["footstep", "walk"]),
    (re.compile(r"\b(run|chase|scramble)\b", re.I), ["footstep", "land"]),
    (re.compile(r"(می‌دود|ميدود|می‌پرد|شتاب)", re.I), ["whoosh", "footstep"]),
    (re.compile(r"\b(shock|hit|slam|burn|impact|punch|fight|strike)\b", re.I), ["hit", "punch", "reaction"]),
    (re.compile(r"\b(door|wood|knock)\b", re.I), ["wood", "hit"]),
    (re.compile(r"\b(metal|blade|steel)\b", re.I), ["metal", "hit"]),
    (re.compile(r"\b(soft|whisper|quiet|hold)\b", re.I), ["soft"]),
    (re.compile(r"\b(reveal|discover|open)\b", re.I), ["hit", "generic", "metal"]),
    (re.compile(r"(خند|قهقه|می‌خند|giggl|laugh|chuckl)", re.I), ["laugh", "vocal"]),
    (re.compile(r"(برمی‌دارد|برمیدارد|جعبه|قلم|pickup|grab)", re.I), ["prop", "pickup"]),
    (re.compile(r"(روشن می‌شود|درخش|جادو|فانوس|glow|magic)", re.I), ["magic", "sparkle", "reveal"]),
    (re.compile(r"(لباس|پارچه|cloth|rustle)", re.I), ["cloth", "rustle"]),
    (re.compile(r"(whoosh|پرواز|عبور سریع)", re.I), ["whoosh", "move"]),
)


@lru_cache(maxsize=1)
def load_audio_catalog() -> dict[str, Any]:
    if not _CATALOG.is_file():
        return {"schema": "audio_catalog#v1", "cues": {}}
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def _score_cue(
    cue_id: str,
    row: dict[str, Any],
    *,
    beat: str,
    wanted_tags: set[str],
    emotion: str,
) -> float:
    tags = {str(t).lower() for t in (row.get("tags") or [])}
    beats = {str(b).lower() for b in (row.get("beats") or [])}
    score = 0.0
    if beat and beat.lower() in beats:
        score += 3.0
    score += 1.5 * len(tags & wanted_tags)
    if emotion in {"tense", "angry", "surprised"} and ("punch" in tags or "metal" in tags):
        score += 1.0
    if emotion in {"sad", "neutral"} and ("soft" in tags or "carpet" in tags):
        score += 0.5
    if emotion in {"happy", "joyful"} and ("laugh" in tags or "vocal" in tags):
        score += 1.2
    # Prefer concrete variants over aliases
    if row.get("alias_of"):
        score -= 2.0
    if cue_id.startswith("ambience_") or cue_id == "silence_hold":
        score -= 5.0  # beds handled separately
    return score


def _wanted_tags(action: str, beat: str) -> set[str]:
    wanted: set[str] = set()
    text = action or ""
    for rx, tags in _ACTION_TAGS:
        if rx.search(text):
            wanted.update(tags)
    beat_l = (beat or "").lower()
    if beat_l in {"entrance", "exit"}:
        wanted.update({"footstep", "walk"})
    elif beat_l == "reaction":
        wanted.update({"hit", "soft", "reaction", "vocal", "laugh"})
    elif beat_l == "conflict":
        wanted.update({"hit", "punch", "conflict"})
    elif beat_l == "reveal":
        wanted.update({"hit", "metal", "generic", "prop", "magic"})
    elif beat_l == "quiet_hold":
        wanted.update({"soft"})
    return wanted


def _pick_best(
    cues: dict[str, Any],
    *,
    beat: str,
    action: str,
    emotion: str,
    rng: random.Random,
) -> str | None:
    wanted = _wanted_tags(action, beat)
    ranked: list[tuple[float, str]] = []
    for cue_id, row in cues.items():
        if row.get("role") == "bed":
            continue
        if cue_id in {"ambience_soft", "ambience_tense", "silence_hold"}:
            continue
        # skip pure aliases when target exists
        if row.get("alias_of"):
            continue
        sc = _score_cue(cue_id, row, beat=beat, wanted_tags=wanted, emotion=emotion)
        if sc > 0:
            ranked.append((sc, cue_id))
    if not ranked:
        # fallback: any footstep or any hit
        for cue_id in cues:
            if cues[cue_id].get("alias_of"):
                continue
            if "footstep" in cue_id or "hit_" in cue_id:
                ranked.append((0.1, cue_id))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (-x[0], x[1]))
    top = ranked[:5]
    # slight deterministic jitter among top matches
    return rng.choice([c for _, c in top])


def _bed_for_beat(beat: str, cues: dict[str, Any]) -> str | None:
    b = (beat or "").lower()
    if b in {"reaction", "conflict"} and "ambience_tense" in cues:
        return "ambience_tense"
    if b in {"entrance", "quiet_hold", "decision", "exit", "reveal"} and "ambience_soft" in cues:
        return "ambience_soft"
    if b == "quiet_hold" and "silence_hold" in cues:
        return "silence_hold"
    return "ambience_soft" if "ambience_soft" in cues else None


def _contacts_for_shot(contacts: list[dict[str, Any]] | None, sid: Any) -> list[dict[str, Any]]:
    if not contacts:
        return []
    return [c for c in contacts if c.get("shot_id") == sid]


def _pick_contact_frame(
    shot_contacts: list[dict[str, Any]],
    cue_id: str,
    *,
    cursor: int,
    dur: int,
) -> tuple[int, str]:
    """Return (global_start_frame, reason). Prefer impact for hits, foot for footsteps."""
    if not shot_contacts:
        return cursor + max(0, min(6, dur // 4)), "fallback_quarter"

    def locals_of(*kinds: str) -> list[int]:
        return [int(c["frame"]) for c in shot_contacts if c.get("kind") in kinds]

    if "footstep" in cue_id or "land" in cue_id:
        feet = locals_of("foot_L", "foot_R", "landing")
        if feet:
            return cursor + feet[0], f"contact_lock:{feet[0]}"
    if any(x in cue_id for x in ("hit_", "stinger", "punch", "impact")):
        hits = locals_of("impact", "landing")
        if hits:
            return cursor + hits[0], f"contact_lock:{hits[0]}"
    # any contact
    f0 = int(shot_contacts[0]["frame"])
    return cursor + f0, f"contact_lock:{f0}"


def run_audio_cue_agent(
    shots: list[dict[str, Any]],
    *,
    fps: int = 24,
    emotion: str = "neutral",
    seed: int | None = None,
    contacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build an audio_cue_plan from narrative shots using only catalog cue_ids.

    Honors explicit ``sfx`` from script breakdown/screenplay when present.
    When ``contacts`` from ContactLockAgent are provided, footstep/hit oneshots
    lock to contact frames (±0) instead of arbitrary quarter-shot offsets.
    """
    try:
        from tools.audio_cues import ensure_audio_cue_files

        ensure_audio_cue_files()
    except Exception:  # noqa: BLE001
        pass
    catalog = load_audio_catalog()
    cues = dict(catalog.get("cues") or {})
    # Invalidate cache if catalog grew narrative stubs mid-process
    load_audio_catalog.cache_clear()
    catalog = load_audio_catalog()
    cues = dict(catalog.get("cues") or {})
    rng = random.Random(seed if seed is not None else 17)
    events: list[dict[str, Any]] = []
    cursor = 0
    notes: list[str] = []

    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        beat = str(sh.get("story_beat") or sh.get("storyBeat") or "decision")
        action = str(sh.get("action") or sh.get("idea") or "")
        dur = int(
            sh.get("duration_frames")
            or sh.get("durationFrames")
            or max(12, round(float(sh.get("duration_sec") or sh.get("durationSec") or 3) * fps))
        )
        shot_contacts = _contacts_for_shot(contacts, sid)

        bed = _bed_for_beat(beat, cues)
        if bed:
            row = cues[bed]
            events.append(
                {
                    "cue": bed,
                    "file": f"audio/{Path(str(row.get('file') or '')).name}",
                    "startFrame": cursor,
                    "durationFrames": dur,
                    "shotId": sid,
                    "gainDb": float(row.get("gain_db") or -18),
                    "loop": True,
                    "role": "bed",
                    "reason": f"bed_for_beat={beat}",
                }
            )

        explicit = list(sh.get("sfx") or sh.get("SFX") or [])
        emitted_oneshot = False
        if explicit:
            for item in explicit:
                if not isinstance(item, dict):
                    continue
                cue_id = str(item.get("cue_id") or item.get("cue") or "")
                if not cue_id or cue_id not in cues:
                    continue
                row = cues[cue_id]
                frac = float(item.get("offset_frac") if item.get("offset_frac") is not None else 0.25)
                frac = max(0.0, min(1.0, frac))
                start = cursor + int(round(frac * dur))
                # Prefer contact lock for footsteps/hits when available
                if shot_contacts and (
                    "footstep" in cue_id or "hit_" in cue_id or "land" in cue_id
                ):
                    start, reason = _pick_contact_frame(
                        shot_contacts, cue_id, cursor=cursor, dur=dur
                    )
                else:
                    reason = f"screenplay_sfx@{frac:.2f}"
                events.append(
                    {
                        "cue": cue_id,
                        "file": f"audio/{Path(str(row.get('file') or '')).name}",
                        "startFrame": start,
                        "durationFrames": None,
                        "shotId": sid,
                        "gainDb": float(row.get("gain_db") or -8),
                        "loop": False,
                        "role": "oneshot",
                        "reason": reason,
                    }
                )
                notes.append(f"shot{sid}:{cue_id}@{reason}")
                emitted_oneshot = True
                if "footstep" in cue_id:
                    for c in shot_contacts:
                        if not str(c.get("kind", "")).startswith("foot"):
                            continue
                        gf = cursor + int(c["frame"])
                        if gf == start:
                            continue
                        events.append(
                            {
                                "cue": cue_id,
                                "file": f"audio/{Path(str(row.get('file') or '')).name}",
                                "startFrame": gf,
                                "durationFrames": None,
                                "shotId": sid,
                                "gainDb": float(row.get("gain_db") or -8),
                                "loop": False,
                                "role": "oneshot",
                                "reason": f"contact_lock:{c['frame']}",
                            }
                        )

        if not emitted_oneshot:
            oneshot = _pick_best(
                cues, beat=beat, action=action, emotion=emotion, rng=rng
            )
            if oneshot:
                row = cues[oneshot]
                start, reason = _pick_contact_frame(
                    shot_contacts, oneshot, cursor=cursor, dur=dur
                )
                events.append(
                    {
                        "cue": oneshot,
                        "file": f"audio/{Path(str(row.get('file') or '')).name}",
                        "startFrame": start,
                        "durationFrames": None,
                        "shotId": sid,
                        "gainDb": float(row.get("gain_db") or -8),
                        "loop": False,
                        "role": "oneshot",
                        "reason": reason,
                    }
                )
                notes.append(f"shot{sid}:{oneshot}@{reason}")
                emitted_oneshot = True

                # Extra footsteps on remaining foot contacts (walk cycles)
                if "footstep" in oneshot:
                    for c in shot_contacts:
                        if not str(c.get("kind", "")).startswith("foot"):
                            continue
                        gf = cursor + int(c["frame"])
                        if gf == start:
                            continue
                        events.append(
                            {
                                "cue": oneshot,
                                "file": f"audio/{Path(str(row.get('file') or '')).name}",
                                "startFrame": gf,
                                "durationFrames": None,
                                "shotId": sid,
                                "gainDb": float(row.get("gain_db") or -8),
                                "loop": False,
                                "role": "oneshot",
                                "reason": f"contact_lock:{c['frame']}",
                            }
                        )
        if not emitted_oneshot:
            notes.append(f"shot{sid}:none")

        cursor += dur

    return {
        "agent": "AudioCueAgent",
        "schema": "audio_cue_plan#v1",
        "fps": fps,
        "emotion": emotion,
        "catalog_source": (catalog.get("source") or {}).get("name"),
        "events": events,
        "totalFrames": cursor,
        "notes": notes,
        "contact_bound": bool(contacts),
        "system_prompt_loaded": False,
    }
