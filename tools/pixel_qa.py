"""
Pixel QA helpers for golden demos (Stage-3).

Uses Pillow + hashlib only (no OpenCV / SSIM deps).
Primary signal: SHA-256 of deterministic slide PNGs.
Secondary: mean absolute difference + structural probes.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FrameDiff:
    path: str
    sha256_actual: str
    sha256_expected: str | None
    mean_abs_diff: float | None
    size_actual: tuple[int, int] | None
    size_expected: tuple[int, int] | None
    ok: bool
    detail: str = ""


@dataclass
class PixelQAReport:
    passed: bool
    compared: int
    failed: int
    diffs: list[FrameDiff] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "compared": self.compared,
            "failed": self.failed,
            "notes": self.notes,
            "diffs": [asdict(d) for d in self.diffs],
        }


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_png_dir(slides_dir: Path | str, *, pattern: str = "slide_*.png") -> dict[str, str]:
    """Return ``{filename: sha256}`` sorted by name."""
    root = Path(slides_dir)
    out: dict[str, str] = {}
    for p in sorted(root.glob(pattern)):
        if p.is_file():
            out[p.name] = sha256_file(p)
    return out


def mean_abs_diff(a: Path | str, b: Path | str) -> float:
    """Per-channel mean absolute difference in 0..255 (RGB)."""
    from PIL import Image
    import statistics

    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    pa = list(ia.getdata())
    pb = list(ib.getdata())
    diffs = [
        abs(ca - cb) for pix_a, pix_b in zip(pa, pb) for ca, cb in zip(pix_a, pix_b)
    ]
    return float(statistics.fmean(diffs)) if diffs else 0.0


def sample_accent_rgb(
    png: Path | str, *, y: int = 6, x_frac: float = 0.5
) -> tuple[int, int, int]:
    """Sample the top accent bar (slideshow paints y=0..12)."""
    from PIL import Image

    img = Image.open(png).convert("RGB")
    w, _h = img.size
    x = max(0, min(w - 1, int(w * x_frac)))
    return img.getpixel((x, y))  # type: ignore[return-value]


def structural_probe(slides_dir: Path | str) -> dict[str, Any]:
    """Slide count, resolution, accent samples — portable without full hashes."""
    from PIL import Image

    root = Path(slides_dir)
    slides = sorted(root.glob("slide_*.png"))
    if not slides:
        return {"slide_count": 0}
    with Image.open(slides[0]) as im:
        size = im.size
    return {
        "slide_count": len(slides),
        "resolution": list(size),
        "accent_rgb_first": list(sample_accent_rgb(slides[0])),
        "accent_rgb_last": list(sample_accent_rgb(slides[-1])),
        "names": [p.name for p in slides],
    }


def write_hashes_json(path: Path | str, hashes: dict[str, str], **extra: Any) -> Path:
    out = Path(path)
    payload = {"hashes": hashes, **extra}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def load_hashes_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_hashes(
    actual: dict[str, str],
    expected: dict[str, str],
) -> PixelQAReport:
    diffs: list[FrameDiff] = []
    names = sorted(set(actual) | set(expected))
    failed = 0
    for name in names:
        a = actual.get(name)
        e = expected.get(name)
        ok = a is not None and e is not None and a == e
        if not ok:
            failed += 1
        diffs.append(
            FrameDiff(
                path=name,
                sha256_actual=a or "",
                sha256_expected=e,
                mean_abs_diff=None,
                size_actual=None,
                size_expected=None,
                ok=ok,
                detail="hash mismatch" if not ok else "ok",
            )
        )
    return PixelQAReport(
        passed=failed == 0 and bool(names),
        compared=len(names),
        failed=failed,
        diffs=diffs,
        notes="sha256 slide compare",
    )


def compare_png_dirs(
    actual_dir: Path | str,
    expected_dir: Path | str,
    *,
    mad_tolerance: float = 0.0,
    pattern: str = "slide_*.png",
) -> PixelQAReport:
    """
    Compare PNGs by hash; if ``mad_tolerance > 0`` and hashes differ,
    allow pass when mean abs diff <= tolerance.
    """
    act_root = Path(actual_dir)
    exp_root = Path(expected_dir)
    actual_files = {p.name: p for p in act_root.glob(pattern) if p.is_file()}
    expected_files = {p.name: p for p in exp_root.glob(pattern) if p.is_file()}
    names = sorted(set(actual_files) | set(expected_files))
    diffs: list[FrameDiff] = []
    failed = 0
    for name in names:
        ap = actual_files.get(name)
        ep = expected_files.get(name)
        if ap is None or ep is None:
            failed += 1
            diffs.append(
                FrameDiff(
                    path=name,
                    sha256_actual=sha256_file(ap) if ap else "",
                    sha256_expected=sha256_file(ep) if ep else None,
                    mean_abs_diff=None,
                    size_actual=None,
                    size_expected=None,
                    ok=False,
                    detail="missing file",
                )
            )
            continue
        ha, he = sha256_file(ap), sha256_file(ep)
        mad = None
        ok = ha == he
        detail = "ok"
        if not ok and mad_tolerance > 0:
            mad = mean_abs_diff(ap, ep)
            ok = mad <= mad_tolerance
            detail = f"mad={mad:.3f} tol={mad_tolerance}"
        elif not ok:
            detail = "hash mismatch"
            if mad_tolerance >= 0:
                try:
                    mad = mean_abs_diff(ap, ep)
                except Exception:  # noqa: BLE001
                    mad = None
        if not ok:
            failed += 1
        from PIL import Image

        with Image.open(ap) as ia, Image.open(ep) as ie:
            size_a, size_e = ia.size, ie.size
        diffs.append(
            FrameDiff(
                path=name,
                sha256_actual=ha,
                sha256_expected=he,
                mean_abs_diff=mad,
                size_actual=size_a,
                size_expected=size_e,
                ok=ok,
                detail=detail,
            )
        )
    return PixelQAReport(
        passed=failed == 0 and bool(names),
        compared=len(names),
        failed=failed,
        diffs=diffs,
        notes="png dir compare",
    )


def extract_mp4_frame(
    mp4: Path | str,
    out_png: Path | str,
    *,
    ffmpeg: str,
    time_sec: float = 0.5,
) -> Path:
    """Extract a single RGB frame from MP4 via ffmpeg."""
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(time_sec),
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(
            "ffmpeg frame extract failed:\n"
            + (proc.stderr or proc.stdout or "unknown")[-1500:]
        )
    return out.resolve()


def compare_structural(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> PixelQAReport:
    """Compare slide_count / resolution / accent RGB from structural probes."""
    diffs: list[FrameDiff] = []
    failed = 0
    for key in ("slide_count", "resolution", "accent_rgb_first", "accent_rgb_last"):
        a, e = actual.get(key), expected.get(key)
        ok = a == e
        if not ok:
            failed += 1
        diffs.append(
            FrameDiff(
                path=key,
                sha256_actual=json.dumps(a),
                sha256_expected=json.dumps(e) if e is not None else None,
                mean_abs_diff=None,
                size_actual=None,
                size_expected=None,
                ok=ok,
                detail="ok" if ok else f"actual={a!r} expected={e!r}",
            )
        )
    return PixelQAReport(
        passed=failed == 0,
        compared=len(diffs),
        failed=failed,
        diffs=diffs,
        notes="structural probe",
    )
