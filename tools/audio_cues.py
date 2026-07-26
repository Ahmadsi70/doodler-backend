"""
Audio drama cues — procedural beds/foley + import licensed WAVs.

Why: silent films feel unfinished; Remotion needs real files under public/audio.
"""

from __future__ import annotations

import json
import math
import shutil
import wave
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_LIB_AUDIO = _ROOT / "libraries" / "audio"
_FILES = _LIB_AUDIO / "files"
_CUES_JSON = _LIB_AUDIO / "cues.json"

# cue_id → (freq_hz, duration_sec, volume, kind)
_TONE_RECIPES: dict[str, tuple[float, float, float, str]] = {
    "ambience_soft": (95.0, 2.4, 0.12, "bed"),
    "ambience_tense": (62.0, 2.4, 0.14, "bed"),
    "foley_footstep": (190.0, 0.14, 0.42, "foley"),
    "foley_hit_soft": (280.0, 0.2, 0.48, "foley"),
    "stinger_reveal": (523.0, 0.55, 0.3, "tone"),
    "silence_hold": (0.0, 0.4, 0.0, "silence"),
    "vocal_laugh": (420.0, 0.55, 0.38, "vocal"),
    "vocal_giggle": (520.0, 0.35, 0.32, "vocal"),
    "vocal_cheer": (660.0, 0.7, 0.4, "vocal"),
    "whoosh_move": (180.0, 0.28, 0.36, "whoosh"),
    "prop_pickup": (310.0, 0.18, 0.4, "foley"),
    "cloth_rustle": (240.0, 0.22, 0.28, "whoosh"),
    "magic_sparkle": (880.0, 0.45, 0.28, "chime"),
    "treasure_chime": (660.0, 0.35, 0.32, "chime"),
}

_BED_CUES = {"ambience_soft", "ambience_tense"}

_NARRATIVE_META: dict[str, dict[str, Any]] = {
    "vocal_laugh": {
        "role": "oneshot",
        "tags": ["vocal", "laugh", "narrative", "procedural"],
        "beats": ["reaction", "decision"],
        "gain_db": -8,
    },
    "vocal_giggle": {
        "role": "oneshot",
        "tags": ["vocal", "giggle", "laugh", "narrative", "procedural"],
        "beats": ["reaction"],
        "gain_db": -9,
    },
    "whoosh_move": {
        "role": "oneshot",
        "tags": ["whoosh", "move", "narrative", "procedural"],
        "beats": ["entrance", "exit", "conflict"],
        "gain_db": -11,
    },
    "prop_pickup": {
        "role": "oneshot",
        "tags": ["prop", "pickup", "foley", "narrative", "procedural"],
        "beats": ["reveal", "decision"],
        "gain_db": -9,
    },
    "cloth_rustle": {
        "role": "oneshot",
        "tags": ["cloth", "rustle", "narrative", "procedural"],
        "beats": ["entrance", "exit"],
        "gain_db": -12,
    },
    "magic_sparkle": {
        "role": "oneshot",
        "tags": ["magic", "sparkle", "reveal", "narrative", "procedural"],
        "beats": ["reveal", "decision", "celebration"],
        "gain_db": -10,
    },
    "vocal_cheer": {
        "role": "oneshot",
        "tags": ["vocal", "cheer", "celebration", "narrative", "procedural"],
        "beats": ["decision", "exit", "celebration", "triumph"],
        "gain_db": -7,
    },
    "treasure_chime": {
        "role": "oneshot",
        "tags": ["chime", "treasure", "reveal", "narrative", "procedural"],
        "beats": ["reveal", "decision", "celebration"],
        "gain_db": -8,
    },
}


def _write_tone_wav(
    path: Path,
    *,
    freq: float,
    duration_sec: float,
    volume: float,
    sample_rate: int = 22050,
    kind: str = "tone",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, int(sample_rate * duration_sec))
    frames = bytearray()
    state = 1234567 + int(freq * 10)

    def _noise() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return (state / 0x7FFFFFFF) * 2.0 - 1.0

    for i in range(n):
        t = i / sample_rate
        env = min(1.0, i / max(1, int(sample_rate * 0.015))) * min(
            1.0, (n - i) / max(1, int(sample_rate * 0.04))
        )
        if kind == "silence" or volume <= 0:
            sample = 0.0
        elif kind == "bed":
            brown = (_noise() + _noise()) * 0.5
            hum = math.sin(2 * math.pi * max(40.0, freq) * t) * 0.35
            sample = (brown * 0.55 + hum * 0.45) * volume * (0.7 + 0.3 * env)
        elif kind == "foley":
            burst = math.exp(-t * 28.0)
            click = math.sin(2 * math.pi * freq * t) * burst
            thump = math.sin(2 * math.pi * (freq * 0.35) * t) * burst * 0.6
            sample = (click + thump + _noise() * 0.08 * burst) * volume
        elif kind == "whoosh":
            # Rising noise sweep — motion / cloth / air
            sweep = freq * (0.6 + 1.8 * (t / max(1e-6, duration_sec)))
            sample = (
                _noise() * math.exp(-t * 6.0) * 0.7
                + math.sin(2 * math.pi * sweep * t) * math.exp(-t * 9.0) * 0.35
            ) * volume * env
        elif kind == "vocal":
            # Soft pulsed tone — placeholder laugh/giggle until CC0 import
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 7.0 * t)
            formant = math.sin(2 * math.pi * freq * t) * 0.55 + math.sin(
                2 * math.pi * (freq * 1.6) * t
            ) * 0.25
            sample = formant * pulse * volume * env
        elif kind == "chime":
            sample = (
                math.sin(2 * math.pi * freq * t) * math.exp(-t * 4.0)
                + math.sin(2 * math.pi * (freq * 1.5) * t) * math.exp(-t * 5.0) * 0.4
            ) * volume
        else:
            sample = math.sin(2 * math.pi * freq * t) * volume * env
        val = int(max(-1.0, min(1.0, sample)) * 32767)
        frames += int(val).to_bytes(2, byteorder="little", signed=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


def load_cues_manifest() -> dict[str, Any]:
    if not _CUES_JSON.is_file():
        return {"schema": "audio_drama_cues#v1", "cues": {}}
    return json.loads(_CUES_JSON.read_text(encoding="utf-8"))


def ensure_audio_cue_files(*, force: bool = False) -> dict[str, str]:
    """Ensure procedural WAV files exist and update cues.json paths."""
    _FILES.mkdir(parents=True, exist_ok=True)
    manifest = load_cues_manifest()
    cues = dict(manifest.get("cues") or {})
    out: dict[str, str] = {}
    for cue_id, recipe in _TONE_RECIPES.items():
        dest = _FILES / f"{cue_id}.wav"
        existing = cues.get(cue_id) or {}
        # Do not clobber Kenney catalog imports / aliases
        if existing.get("alias_of") or existing.get("attribution") or (
            isinstance(existing.get("tags"), list) and "kenney" in existing["tags"]
        ):
            if existing.get("file"):
                out[cue_id] = str((_LIB_AUDIO / str(existing["file"])).resolve())
            continue
        target_file = existing.get("file")
        if target_file and target_file != f"files/{cue_id}.wav":
            # alias pointing at another wav
            out[cue_id] = str((_LIB_AUDIO / str(target_file)).resolve())
            continue
        if force or not dest.is_file() or dest.stat().st_size < 44:
            _write_tone_wav(
                dest,
                freq=recipe[0],
                duration_sec=recipe[1],
                volume=recipe[2],
                kind=recipe[3],
            )
        rel = f"files/{cue_id}.wav"
        row = dict(existing)
        row["file"] = rel
        if cue_id in _BED_CUES:
            row["role"] = "bed"
            row["loop"] = True
        meta = _NARRATIVE_META.get(cue_id)
        if meta:
            for k, v in meta.items():
                row.setdefault(k, v)
            row["license"] = row.get("license") or "procedural-stub"
            row["attribution"] = row.get("attribution") or "Story procedural stub"
        cues[cue_id] = row
        out[cue_id] = str(dest.resolve())
    manifest["cues"] = cues
    manifest["notes"] = (
        "Procedural beds/foley + narrative stubs. Replace via import_cue_wav() with CC0 assets."
    )
    _CUES_JSON.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _merge_narrative_into_catalog()
    return out


def _merge_narrative_into_catalog() -> None:
    """Upsert narrative procedural cue metadata into catalog.json for AudioCueAgent."""
    catalog_path = _LIB_AUDIO / "catalog.json"
    if not catalog_path.is_file():
        return
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    cues = dict(catalog.get("cues") or {})
    changed = False
    for cue_id, meta in _NARRATIVE_META.items():
        dest = _FILES / f"{cue_id}.wav"
        if not dest.is_file():
            continue
        row = dict(cues.get(cue_id) or {})
        if row.get("alias_of") or (
            isinstance(row.get("tags"), list) and "kenney" in row["tags"]
        ):
            continue
        for k, v in meta.items():
            row[k] = v
        row["file"] = f"files/{cue_id}.wav"
        row["loop"] = False
        row["license"] = row.get("license") or "procedural-stub"
        row["attribution"] = row.get("attribution") or "Story procedural stub"
        cues[cue_id] = row
        changed = True
    if not changed:
        return
    catalog["cues"] = cues
    sources = catalog.get("sources")
    if not isinstance(sources, list):
        sources = [catalog.get("source")] if catalog.get("source") else []
    if not any(
        isinstance(s, dict) and s.get("name") == "Story narrative stubs" for s in sources
    ):
        sources.append(
            {
                "name": "Story narrative stubs",
                "license": "procedural-stub (replace with CC0)",
                "note": "vocal/whoosh/prop placeholders for silent narrative",
            }
        )
    catalog["sources"] = sources
    catalog_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def import_cue_wav(cue_id: str, src: Path | str) -> Path:
    """Replace a cue file with a user-provided WAV (keeps cue id)."""
    src_p = Path(src)
    if not src_p.is_file():
        raise FileNotFoundError(src_p)
    ensure_audio_cue_files()
    dest = _FILES / f"{cue_id}.wav"
    shutil.copy2(src_p, dest)
    man = load_cues_manifest()
    cues = dict(man.get("cues") or {})
    row = dict(cues.get(cue_id) or {})
    row["file"] = f"files/{cue_id}.wav"
    row["imported"] = True
    cues[cue_id] = row
    man["cues"] = cues
    _CUES_JSON.write_text(
        json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sync_cues_to_remotion_public()
    return dest.resolve()


def cues_for_beat(beat: str) -> list[str]:
    man = load_cues_manifest()
    b = (beat or "").lower()
    ids: list[str] = []
    for cue_id, row in (man.get("cues") or {}).items():
        beats = [str(x).lower() for x in (row.get("beats") or [])]
        if b in beats or "*" in beats:
            ids.append(cue_id)
    return ids


def build_audio_timeline(
    shots: list[dict[str, Any]],
    *,
    fps: int = 24,
) -> dict[str, Any]:
    """Map story beats → cue events; beds get role=bed and span the shot."""
    ensure_audio_cue_files()
    man = load_cues_manifest()
    events: list[dict[str, Any]] = []
    cursor = 0
    for sh in shots:
        beat = str(sh.get("storyBeat") or sh.get("story_beat") or "")
        dur = int(
            sh.get("durationFrames")
            or max(12, round(float(sh.get("durationSec") or 3) * fps))
        )
        for cue_id in cues_for_beat(beat):
            row = (man.get("cues") or {}).get(cue_id) or {}
            rel = row.get("file")
            if not rel:
                continue
            role = "bed" if cue_id in _BED_CUES or row.get("role") == "bed" else "oneshot"
            events.append(
                {
                    "cue": cue_id,
                    "file": f"audio/{Path(str(rel)).name}",
                    "startFrame": cursor,
                    "durationFrames": dur if role == "bed" else None,
                    "shotId": sh.get("shotId", sh.get("shot_id")),
                    "gainDb": float(row.get("gain_db") or (-18 if role == "bed" else -10)),
                    "loop": bool(row.get("loop") or role == "bed"),
                    "role": role,
                }
            )
        cursor += dur
    return {
        "schema": "audio_timeline#v1",
        "fps": fps,
        "events": events,
        "totalFrames": cursor,
    }


def build_audio_timeline_from_plan(
    plan: dict[str, Any],
    shots: list[dict[str, Any]] | None = None,
    *,
    fps: int = 24,
) -> dict[str, Any]:
    """Materialize Remotion audioTimeline from AudioCueAgent plan."""
    sync_cues_to_remotion_public()
    events = []
    for ev in plan.get("events") or []:
        if not isinstance(ev, dict):
            continue
        cue = str(ev.get("cue") or "")
        raw_file = str(ev.get("file") or "")
        name = Path(raw_file).name if raw_file else f"{cue}.wav"
        if not name.endswith(".wav") and cue:
            name = f"{cue}.wav"
        events.append(
            {
                "cue": cue,
                "file": f"audio/{name}",
                "startFrame": int(ev.get("startFrame") or 0),
                "durationFrames": ev.get("durationFrames"),
                "shotId": ev.get("shotId"),
                "gainDb": float(ev.get("gainDb") or -12),
                "loop": bool(ev.get("loop")),
                "role": ev.get("role") or "oneshot",
                "reason": ev.get("reason"),
            }
        )
    total = int(plan.get("totalFrames") or 0)
    if not total and shots:
        total = sum(
            int(s.get("durationFrames") or max(12, round(float(s.get("durationSec") or 3) * fps)))
            for s in shots
        )
    return {
        "schema": "audio_timeline#v1",
        "fps": int(plan.get("fps") or fps),
        "events": events,
        "totalFrames": total,
        "agent": plan.get("agent") or "AudioCueAgent",
        "notes": list(plan.get("notes") or []),
    }


def sync_cues_to_remotion_public() -> Path:
    """Copy libraries/audio/files/*.wav → remotion/public/audio/."""
    ensure_audio_cue_files()
    dest = _ROOT / "remotion" / "public" / "audio"
    dest.mkdir(parents=True, exist_ok=True)
    for src in _FILES.glob("*.wav"):
        (dest / src.name).write_bytes(src.read_bytes())
    return dest
