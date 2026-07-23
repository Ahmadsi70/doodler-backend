"""
PhonemeSyncAgent — VO lip-sync markers (visual lead ≤2 frames @ 24fps).

Why: SceneIR already models PhonemeMarker; Remotion mouth must open before
audio (Williams). No ASR — grapheme→viseme from dialogue / quoted action.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

LeadFrames = Literal[1, 2]

# Grapheme → Preston-Blair-ish viseme id
_SHAPE: dict[str, str] = {
    "a": "A",
    "á": "A",
    "à": "A",
    "e": "E",
    "é": "E",
    "i": "I",
    "í": "I",
    "y": "I",
    "o": "O",
    "ó": "O",
    "u": "U",
    "ú": "U",
    "w": "U",
    "m": "M",
    "b": "M",
    "p": "M",
    "f": "F",
    "v": "F",
    "l": "L",
    "r": "L",
    "th": "TH",
    "s": "S",
    "z": "S",
    "c": "S",
    "t": "T",
    "d": "T",
    "n": "T",
    "k": "T",
    "g": "T",
    "q": "T",
    "x": "T",
    "h": "rest",
    "j": "E",
}

_MOUTH_OPEN: dict[str, float] = {
    "rest": 0.05,
    "M": 0.0,
    "F": 0.15,
    "T": 0.2,
    "S": 0.25,
    "TH": 0.22,
    "L": 0.3,
    "E": 0.4,
    "I": 0.45,
    "U": 0.5,
    "O": 0.65,
    "A": 0.85,
}

_QUOTE_RE = re.compile(r'[«"“]([^»"”]+)[»"”]|\'([^\']+)\'')
_VO_NOTE_RE = re.compile(r"(?:^|\b)(?:VO|dialogue)\s*:\s*(.+)", re.I)


def extract_dialogue(sh: dict[str, Any]) -> str:
    """Prefer explicit dialogue/vo_text; else quotes in action; else VO: notes."""
    for key in ("dialogue", "vo_text", "voText", "line"):
        val = sh.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    action = str(sh.get("action") or sh.get("idea") or "")
    m = _QUOTE_RE.search(action)
    if m:
        return (m.group(1) or m.group(2) or "").strip()
    notes = str(sh.get("notes") or "")
    m2 = _VO_NOTE_RE.search(notes)
    if m2:
        return m2.group(1).strip()
    return ""


def _tokenizeize(text: str) -> list[tuple[str, str]]:
    """Return (token, shape) list; multi-letter digraphs first."""
    t = re.sub(r"[^a-zA-Záéíóúàèù\s']+", " ", text.lower())
    out: list[tuple[str, str]] = []
    i = 0
    s = t.replace("'", "")
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        if s[i : i + 2] == "th":
            out.append(("th", "TH"))
            i += 2
            continue
        ch = s[i]
        shape = _SHAPE.get(ch, "rest")
        out.append((ch, shape))
        i += 1
    return out


def _frames_per_phone(n_phones: int, speak_frames: int) -> int:
    if n_phones <= 0:
        return 2
    return max(1, min(4, speak_frames // max(1, n_phones)))


def run_phoneme_sync_agent(
    shots: list[dict[str, Any]],
    *,
    fps: int = 24,
    lead_frames: LeadFrames = 2,
) -> dict[str, Any]:
    """
    Emit phoneme_sync#v1 markers aligned to SceneIR PhonemeMarker contract.

    Inactive (empty phonemes) when no dialogue/VO text is present.
    """
    lead = 1 if int(lead_frames) <= 1 else 2
    phonemes: list[dict[str, Any]] = []
    shot_rows: list[dict[str, Any]] = []

    cursor = 0
    for i, sh in enumerate(shots):
        sid = sh.get("shot_id", sh.get("shotId", i))
        dur = int(
            sh.get("duration_frames")
            or sh.get("durationFrames")
            or max(12, round(float(sh.get("duration_sec") or sh.get("durationSec") or 3) * fps))
        )
        ant = int(sh.get("anticipation_frames") or sh.get("anticipationFrames") or 6)
        hold = int(sh.get("hold_frames") or sh.get("holdFrames") or 12)
        dialogue = extract_dialogue(sh)
        local_phones: list[dict[str, Any]] = []
        align_method: str | None = None
        if dialogue:
            tokens = _tokenizeize(dialogue)
            speak_start = min(ant, max(0, dur - 4))
            vo_path = str(sh.get("vo_path") or sh.get("voPath") or "")
            vo_frames = int(
                sh.get("vo_duration_frames")
                or sh.get("voDurationFrames")
                or 0
            )
            if not vo_frames and vo_path:
                try:
                    from tools.vo_audio import duration_frames_for_wav

                    vo_frames = duration_frames_for_wav(vo_path, fps=fps)
                except Exception:  # noqa: BLE001
                    vo_frames = 0

            aligned_rows: list[dict[str, Any]] = []
            if vo_path and Path(vo_path).is_file():
                try:
                    from tools.vo_align import align_dialogue_to_wav

                    aligned_rows = align_dialogue_to_wav(
                        dialogue,
                        vo_path,
                        fps=fps,
                        lead_frames=lead,
                        speak_start=speak_start,
                    )
                except Exception:  # noqa: BLE001
                    aligned_rows = []

            if aligned_rows:
                align_method = str(aligned_rows[0].get("method") or "energy")
                for a in aligned_rows:
                    audio_f = max(0, min(dur - 1, int(a["audio_frame"])))
                    visual_f = max(0, min(audio_f, int(a["visual_frame"])))
                    shape = str(a.get("shape") or "rest")
                    row = {
                        "shot_id": sid,
                        "token": a.get("token"),
                        "shape": shape,
                        "audio_frame": audio_f,
                        "visual_frame": visual_f,
                        "global_audio_frame": cursor + audio_f,
                        "global_visual_frame": cursor + visual_f,
                        "lead_frames": lead,
                        "mouth": float(_MOUTH_OPEN.get(shape, 0.3)),
                        "aligned": True,
                        "method": align_method,
                    }
                    local_phones.append(row)
                    phonemes.append(row)
                rest_f = min(dur - 1, max(int(aligned_rows[-1]["audio_frame"]) + 1, speak_start + 1))
            else:
                if vo_frames > 0:
                    speak_end = min(dur, speak_start + vo_frames)
                else:
                    speak_end = max(speak_start + 1, dur - max(2, hold // 2))
                speak_frames = max(1, speak_end - speak_start)
                step = _frames_per_phone(len(tokens), speak_frames)
                t = speak_start
                for token, shape in tokens:
                    if t >= speak_end:
                        break
                    audio_f = t
                    visual_f = max(0, audio_f - lead)
                    row = {
                        "shot_id": sid,
                        "token": token,
                        "shape": shape,
                        "audio_frame": audio_f,
                        "visual_frame": visual_f,
                        "global_audio_frame": cursor + audio_f,
                        "global_visual_frame": cursor + visual_f,
                        "lead_frames": lead,
                        "mouth": float(_MOUTH_OPEN.get(shape, 0.3)),
                        "aligned": False,
                        "method": "grapheme",
                    }
                    local_phones.append(row)
                    phonemes.append(row)
                    t += step
                rest_f = min(dur - 1, max(t, speak_end - 1))
            rest = {
                "shot_id": sid,
                "token": "_",
                "shape": "rest",
                "audio_frame": rest_f,
                "visual_frame": max(0, rest_f - lead),
                "global_audio_frame": cursor + rest_f,
                "global_visual_frame": cursor + max(0, rest_f - lead),
                "lead_frames": lead,
                "mouth": float(_MOUTH_OPEN["rest"]),
                "aligned": bool(aligned_rows),
                "method": align_method or "grapheme",
            }
            local_phones.append(rest)
            phonemes.append(rest)
        shot_rows.append(
            {
                "shot_id": sid,
                "dialogue": dialogue,
                "phoneme_count": len(local_phones),
                "duration_frames": dur,
                "align_method": align_method,
            }
        )
        cursor += dur

    methods = {s.get("align_method") for s in shot_rows if s.get("align_method")}
    primary = "whisper" if "whisper" in methods else ("energy" if "energy" in methods else None)

    return {
        "agent": "PhonemeSyncAgent",
        "schema": "phoneme_sync#v1",
        "fps": fps,
        "lead_frames": lead,
        "active": bool(phonemes),
        "align_method": primary,
        "phonemes": phonemes,
        "shots": shot_rows,
        "notes": [
            f"active={bool(phonemes)}",
            f"phonemes={len(phonemes)}",
            f"lead={lead}",
            f"align={primary or 'grapheme'}",
        ],
    }


def mouth_curve_for_shot(
    phoneme_sync: dict[str, Any] | None,
    shot_id: Any,
) -> list[dict[str, Any]] | None:
    """Build mouth keyframes for Remotion expressionCurve (visual_frame timed)."""
    if not phoneme_sync or not phoneme_sync.get("active"):
        return None
    rows = [p for p in phoneme_sync.get("phonemes") or [] if p.get("shot_id") == shot_id]
    if not rows:
        return None
    curve: list[dict[str, Any]] = [{"frame": 0, "mouth": 0.05, "eyesOpen": 1.0, "brows": 0.0}]
    for p in sorted(rows, key=lambda x: int(x["visual_frame"])):
        curve.append(
            {
                "frame": int(p["visual_frame"]),
                "mouth": float(p.get("mouth") or _MOUTH_OPEN.get(str(p.get("shape")), 0.3)),
                "shape": p.get("shape"),
            }
        )
    # Deduplicate frames (last wins)
    by_f: dict[int, dict[str, Any]] = {}
    for c in curve:
        by_f[int(c["frame"])] = c
    return [by_f[f] for f in sorted(by_f)]


def merge_mouth_into_expression_curve(
    expression_curve: list[dict[str, Any]] | None,
    mouth_curve: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Overlay mouth values onto acting-lead expression curve."""
    if not mouth_curve:
        return expression_curve
    if not expression_curve:
        return mouth_curve
    by_f: dict[int, dict[str, Any]] = {int(c["frame"]): dict(c) for c in expression_curve}
    for m in mouth_curve:
        f = int(m["frame"])
        row = dict(by_f.get(f) or {"frame": f})
        row["mouth"] = float(m.get("mouth") or 0)
        if m.get("shape"):
            row["shape"] = m["shape"]
        by_f[f] = row
    return [by_f[f] for f in sorted(by_f)]
