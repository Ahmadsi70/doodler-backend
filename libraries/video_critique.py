"""
Gemini video critique — review a produced Story MP4 for visual weaknesses.

Why: delivery quality needs an automated director pass; Gemini's video
understanding spots seams, style drift, and timing issues humans miss in CI.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

from libraries.gemini_client import (
    _API_ROOT,
    _api_key,
    _model_chain,
    gemini_model_id,
)

CRITIQUE_SCHEMA = "video_critique_v1"

AnalyzeFn = Callable[[Path, str], str]


def critique_prompt(*, story: str = "", language: str = "en") -> str:
    """
    Director rubric for silent narrative / paper-cut composites.

    Asks for structured JSON so the studio can act on weaknesses.
    """
    story_bit = (story or "").strip()[:800]
    lang_note = (
        "Write summary/weaknesses/fix_plan in Persian (fa)."
        if language.startswith("fa")
        else "Write summary/weaknesses/fix_plan in English."
    )
    return f"""You are a senior animation QC director reviewing a silent kids storybook video
produced by an automated pipeline (one full still per page + Ken Burns + crossfade).

Story intent:
{story_bit or "(not provided)"}

Analyze the FULL video carefully. Look for:
- page-to-page style drift or broken crossfades
- shaky / wrong Ken Burns camera (too fast, too static, cropping faces badly)
- missing story beats vs the intent
- text/watermark/dialogue artifacts (should be silent, no on-image text)
- flat or empty holds with no readable page change
- overall professional polish for 1080p delivery

{lang_note}

Return ONLY valid JSON (no markdown fences) with this shape:
{{
  "overall_score": <int 1-10>,
  "summary": "<2-4 sentences>",
  "strengths": ["..."],
  "weaknesses": [
    {{
      "timestamp": "MM:SS",
      "category": "composite|style|timing|placement|story|other",
      "severity": "<what is wrong>",
      "severity": "<concrete fix for the pipeline>"
    }}
  ],
  "fix_plan": ["ordered next engineering steps"]
}}
"""


def parse_critique_json(text: str) -> dict[str, Any]:
    """Parse model JSON; tolerate ``` fences."""
    cleaned = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("critique JSON must be an object")
    data.setdefault("overall_score", 0)
    data.setdefault("summary", "")
    data.setdefault("strengths", [])
    data.setdefault("weaknesses", [])
    data.setdefault("fix_plan", [])
    return data


@dataclass
class VideoCritiqueReport:
    """Structured critique result written next to the video."""

    ok: bool
    schema_version: str = CRITIQUE_SCHEMA
    video_path: str = ""
    backend: str = "mock"
    model: str = ""
    overall_score: int = 0
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[dict[str, Any]] = field(default_factory=list)
    fix_plan: list[str] = field(default_factory=list)
    report_json: Path | None = None
    raw_text: str = ""
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "video_path": self.video_path,
            "backend": self.backend,
            "model": self.model,
            "overall_score": self.overall_score,
            "summary": self.summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "fix_plan": self.fix_plan,
            "error": self.error,
        }


def _mock_critique_text(video: Path, story: str) -> str:
    return json.dumps(
        {
            "overall_score": 5,
            "summary": f"Mock critique for {video.name}. Story: {(story or '')[:80]}",
            "strengths": ["pipeline produced an MP4"],
            "weaknesses": [
                {
                    "timestamp": "00:00",
                    "category": "other",
                    "severity": "mock backend — no live Gemini video pass",
                    "severity": "run with --live and GOOGLE_API_KEY",
                }
            ],
            "fix_plan": ["enable live Gemini Files video critique"],
        }
    )


def upload_gemini_file(path: Path, *, timeout: float = 300.0) -> dict[str, Any]:
    """
    Upload a local file via Gemini Files API (multipart resumable-lite).

    Why: video understanding needs a file_uri; keeps us on httpx without SDK.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    key = _api_key()
    mime = "video/mp4" if path.suffix.lower() == ".mp4" else "application/octet-stream"
    # Simple upload endpoint
    url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={key}"
    meta = json.dumps({"file": {"display_name": path.name}})
    with path.open("rb") as fh:
        files = {
            "metadata": ("metadata.json", meta, "application/json"),
            "file": (path.name, fh, mime),
        }
        resp = httpx.post(url, files=files, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    file_obj = data.get("file") if isinstance(data.get("file"), dict) else data
    if not isinstance(file_obj, dict) or not file_obj.get("uri"):
        raise RuntimeError(f"unexpected Files API response: {str(data)[:400]}")
    return file_obj


def wait_file_active(
    file_name: str,
    *,
    timeout_sec: float = 180.0,
    poll_sec: float = 3.0,
) -> dict[str, Any]:
    """Poll Files API until state == ACTIVE."""
    key = _api_key()
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        url = f"{_API_ROOT}/files/{file_name}?key={key}"
        # file_name may already be "files/xxx"
        name = file_name if file_name.startswith("files/") else f"files/{file_name}"
        url = f"{_API_ROOT}/{name}?key={key}"
        resp = httpx.get(url, timeout=60.0)
        resp.raise_for_status()
        last = resp.json()
        state = str((last.get("state") or "")).upper()
        if state in ("ACTIVE", "STATE_ACTIVE"):
            return last
        if state in ("FAILED", "STATE_FAILED"):
            raise RuntimeError(f"Gemini file processing failed: {last}")
        time.sleep(poll_sec)
    raise TimeoutError(f"Gemini file not ACTIVE in time: {last}")


def _generate_with_file_uri(
    file_uri: str,
    mime_type: str,
    prompt: str,
    *,
    model: str,
    timeout: float,
) -> str:
    url = f"{_API_ROOT}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    parts = (
        ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    )
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned empty critique text")
    return text


def _generate_with_frame_samples(
    video: Path,
    prompt: str,
    *,
    model: str,
    timeout: float,
    max_frames: int = 8,
) -> str:
    """Fallback: sample still frames and send as images."""
    import base64

    import cv2

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idxs = (
        [0]
        if n <= 1
        else [int(i * (n - 1) / (max_frames - 1)) for i in range(max_frames)]
    )
    parts: list[dict[str, Any]] = [{"text": prompt + "\n\n(Keyframe samples attached.)"}]
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        # shrink for token budget
        h, w = fr.shape[:2]
        scale = min(1.0, 960 / float(max(w, 1)))
        if scale < 0.999:
            fr = cv2.resize(fr, (int(w * scale), int(h * scale)))
        ok2, buf = cv2.imencode(".jpg", fr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok2:
            continue
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        parts.append(
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}}
        )
    cap.release()
    if len(parts) < 2:
        raise RuntimeError("no frames extracted for critique fallback")

    url = f"{_API_ROOT}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    out_parts = (
        ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    )
    text = "".join(str(p.get("text") or "") for p in out_parts).strip()
    if not text:
        raise RuntimeError("Gemini returned empty critique text (frames)")
    return text


def gemini_critique_video_text(
    video: Path,
    prompt: str,
    *,
    timeout: float = 300.0,
) -> tuple[str, str, str]:
    """
    Live critique text via Files API, falling back to frame samples.

    Returns (text, backend, model_id).
    """
    video = Path(video)
    last_err: Exception | None = None
    for mid in _model_chain(gemini_model_id()):
        try:
            meta = upload_gemini_file(video, timeout=timeout)
            name = str(meta.get("name") or "")
            uri = str(meta.get("uri") or "")
            mime = str(meta.get("mimeType") or "video/mp4")
            # short name for GET: files/abc
            short = name.split("/")[-1] if name else ""
            if short:
                active = wait_file_active(name if name.startswith("files/") else short)
                uri = str(active.get("uri") or uri)
                mime = str(active.get("mimeType") or mime)
            text = _generate_with_file_uri(
                uri, mime, prompt, model=mid, timeout=timeout
            )
            return text, "gemini_files", mid
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            try:
                text = _generate_with_frame_samples(
                    video, prompt, model=mid, timeout=timeout
                )
                return text, "gemini_frames", mid
            except Exception as exc2:  # noqa: BLE001
                last_err = exc2
                continue
    raise RuntimeError(f"Gemini video critique failed: {last_err}")


def analyze_story_video(
    video_path: str | Path,
    *,
    story: str = "",
    language: str = "en",
    mock: bool = False,
    output_dir: str | Path | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> VideoCritiqueReport:
    """
    Critique a produced MP4 and write ``video_critique.json`` beside it.
    """
    video = Path(video_path)
    out_dir = Path(output_dir) if output_dir else video.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "video_critique.json"
    prompt = critique_prompt(story=story, language=language)

    if not video.is_file() and not mock:
        rep = VideoCritiqueReport(
            ok=False,
            video_path=str(video),
            error=f"video not found: {video}",
            report_json=report_path,
        )
        report_path.write_text(
            json.dumps(rep.to_json(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return rep

    backend = "mock"
    model = "mock"
    raw = ""
    try:
        if mock and analyze_fn is None:
            raw = _mock_critique_text(video, story)
            backend = "mock"
        elif analyze_fn is not None:
            raw = analyze_fn(video, prompt)
            backend = "inject"
        else:
            raw, backend, model = gemini_critique_video_text(video, prompt)
        data = parse_critique_json(raw)
        rep = VideoCritiqueReport(
            ok=True,
            video_path=str(video.resolve()) if video.is_file() else str(video),
            backend=backend,
            model=model,
            overall_score=int(data.get("overall_score") or 0),
            summary=str(data.get("summary") or ""),
            strengths=[str(x) for x in (data.get("strengths") or [])],
            weaknesses=[
                x if isinstance(x, dict) else {"severity": str(x)}
                for x in (data.get("weaknesses") or [])
            ],
            fix_plan=[str(x) for x in (data.get("fix_plan") or [])],
            report_json=report_path,
            raw_text=raw,
        )
    except Exception as exc:  # noqa: BLE001
        rep = VideoCritiqueReport(
            ok=False,
            video_path=str(video),
            backend=backend,
            model=model,
            error=str(exc)[:800],
            report_json=report_path,
            raw_text=raw,
        )

    payload = rep.to_json()
    payload["raw_text"] = rep.raw_text[:12000]
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    rep.report_json = report_path
    return rep
