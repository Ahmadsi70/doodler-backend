"""
Storybook pipeline — pages → stills → Ken Burns + crossfade → MP4.

Why: long silent films fit Gemini stills + camera moves; skip cutout/Telea.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw

from libraries.storybook_contract import StorybookPlan

GenerateStillFn = Callable[[str], bytes | bytearray | str | Path]


def _smootherstep(t: float) -> float:
    x = float(np.clip(t, 0.0, 1.0))
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def ken_burns_frame(
    rgb: np.ndarray,
    *,
    t_norm: float,
    camera: str,
    width: int,
    height: int,
    shot: str = "wide",
) -> np.ndarray:
    """
    Sample a camera window from a page still at normalized time in [0,1].

    Why: shot size + stronger pans make page holds feel directed, not frozen.
    """
    src = np.asarray(rgb)
    if src.ndim != 3:
        raise ValueError("rgb must be HxWx3")
    h0, w0 = src.shape[:2]
    u = _smootherstep(t_norm)
    cam = (camera or "subtle_zoom_in").lower()
    sh = (shot or "wide").lower()

    # Base crop tightness by shot; animate zoom within the hold.
    if sh == "close":
        scale0, scale1 = 1.18, 1.32
    elif sh == "medium":
        scale0, scale1 = 1.08, 1.20
    else:
        scale0, scale1 = 1.02, 1.12

    if cam == "static":
        scale1 = scale0 + 0.03
    elif cam.startswith("slow_pan"):
        # Keep scale mostly steady while panning
        mid = 0.5 * (scale0 + scale1)
        scale0 = scale1 = mid

    scale = scale0 + (scale1 - scale0) * u
    crop_w = max(8, int(round(w0 / scale)))
    crop_h = max(8, int(round(h0 / scale)))
    crop_w = min(crop_w, w0)
    crop_h = min(crop_h, h0)

    max_x = w0 - crop_w
    max_y = h0 - crop_h
    cx0, cy0 = max_x * 0.5, max_y * 0.5
    if cam == "slow_pan_left":
        x0 = int(round(max_x * (0.08 + 0.84 * (1.0 - u))))
        y0 = int(round(cy0))
    elif cam == "slow_pan_right":
        x0 = int(round(max_x * (0.08 + 0.84 * u)))
        y0 = int(round(cy0))
    else:
        # Zoom toward slight upper-third / hero bias
        x0 = int(round(cx0 + (max_x * 0.08) * u))
        y0 = int(round(max(0.0, cy0 - max_y * 0.12 * u)))

    x0 = int(np.clip(x0, 0, max_x))
    y0 = int(np.clip(y0, 0, max_y))
    patch = src[y0 : y0 + crop_h, x0 : x0 + crop_w]
    out = cv2.resize(patch, (width, height), interpolation=cv2.INTER_LANCZOS4)
    return out


def _paint_mock_page(
    prompt: str,
    *,
    width: int,
    height: int,
    index: int,
) -> Image.Image:
    """Deterministic placeholder still when live image backends are off."""
    hue = (index * 37) % 180
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[:, :] = (40 + (hue % 80), 90 + (index * 12) % 100, 140)
    im = Image.fromarray(base)
    draw = ImageDraw.Draw(im)
    margin = max(8, width // 20)
    draw.ellipse(
        [width // 3, height // 3, 2 * width // 3, 2 * height // 3],
        fill=(220, 160, 80),
    )
    draw.rectangle(
        [margin, height - height // 4, width - margin, height - margin],
        fill=(60, 100, 70),
    )
    _ = prompt  # prompt reserved for live path parity
    return im


def _resolve_still_backend(explicit: str | None = None) -> str:
    """Prefer env/CLI still backend; default flux when OpenRouter is available."""
    raw = (
        explicit
        or os.environ.get("STILL_BACKEND")
        or os.environ.get("IMAGE_BACKEND")
        or ""
    ).strip().lower()
    if raw in {"flux", "flux2", "klein", "flux_klein", "openrouter_flux"}:
        return "flux"
    if raw in {"gemini", "openrouter_gemini", "google"}:
        return "gemini"
    if (os.environ.get("OPENROUTER_API_KEY") or "").strip():
        return "flux"
    return "gemini"


def resolve_page_still(
    prompt: str,
    *,
    width: int,
    height: int,
    index: int,
    mock: bool,
    generate_fn: GenerateStillFn | None = None,
    reference_images: list[bytes] | None = None,
    still_backend: str | None = None,
) -> tuple[Image.Image, str]:
    """Return (RGB still, backend tag). Flux primary; Gemini remains fallback."""
    from io import BytesIO

    if generate_fn is not None:
        raw = generate_fn(prompt)
        if isinstance(raw, (str, Path)):
            return Image.open(raw).convert("RGB").resize(
                (width, height), Image.Resampling.LANCZOS
            ), "inject"
        return Image.open(BytesIO(bytes(raw))).convert("RGB").resize(
            (width, height), Image.Resampling.LANCZOS
        ), "inject"
    has_keys = bool(
        (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    )
    if mock or not has_keys:
        return _paint_mock_page(prompt, width=width, height=height, index=index), "paint"

    backend = _resolve_still_backend(still_backend)
    last_err: Exception | None = None

    if backend == "flux":
        try:
            from libraries.flux_client import generate_image as flux_generate

            raw = flux_generate(prompt, reference_images=reference_images)
            return Image.open(BytesIO(raw)).convert("RGB").resize(
                (width, height), Image.Resampling.LANCZOS
            ), "flux"
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    try:
        from libraries.gemini_client import generate_image

        raw = generate_image(prompt, reference_images=reference_images)
        tag = "gemini_fallback" if backend == "flux" and last_err is not None else "gemini"
        return Image.open(BytesIO(raw)).convert("RGB").resize(
            (width, height), Image.Resampling.LANCZOS
        ), tag
    except Exception as exc:  # noqa: BLE001
        last_err = exc
        return _paint_mock_page(prompt, width=width, height=height, index=index), "paint_fallback"


def _page_frame_sequence(
    still_rgb: np.ndarray,
    *,
    hold_sec: float,
    camera: str,
    shot: str,
    fps: int,
    width: int,
    height: int,
    live_draw: bool = False,
    draw_frac: float = 0.55,
    fill_frac: float = 0.38,
    visual_action: str = "",
    draw_budget_sec: float = 3.2,
) -> list[np.ndarray]:
    """
    Build one page's frames.

    With ``live_draw``, a colorful pen tip paints the still (~``draw_budget_sec``);
    the remaining hold shows the finished page with Ken Burns.
    """
    n = max(1, int(round(float(hold_sec) * float(fps))))
    # Work at output size so pen-draw matches the final frame.
    still = ken_burns_frame(
        still_rgb,
        t_norm=0.0,
        camera="static",
        width=width,
        height=height,
        shot=shot,
    )
    if not live_draw:
        frames: list[np.ndarray] = []
        for i in range(n):
            t = 0.0 if n == 1 else i / float(n - 1)
            frames.append(
                ken_burns_frame(
                    still_rgb,
                    t_norm=t,
                    camera=camera,
                    width=width,
                    height=height,
                    shot=shot,
                )
            )
        return frames

    from libraries.storybook_pen_draw import pen_draw_frame_sequence

    # Fast draw: cap paint time so long holds are mostly "show the scene".
    budget = float(np.clip(draw_budget_sec, 1.2, max(1.2, hold_sec * 0.55)))
    draw_n = max(2, int(round(budget * float(fps))))
    draw_n = min(draw_n, max(2, n - 2))
    settle_n = max(1, n - draw_n)
    drawn = pen_draw_frame_sequence(
        still,
        n_frames=draw_n,
        draw_frac=draw_frac,
        fill_frac=fill_frac,
        visual_action=visual_action,
    )
    frames = list(drawn)
    for i in range(settle_n):
        t = 0.0 if settle_n == 1 else i / float(settle_n - 1)
        frames.append(
            ken_burns_frame(
                still_rgb,
                t_norm=t,
                camera=camera,
                width=width,
                height=height,
                shot=shot,
            )
        )
    return frames


def compose_storybook_mp4(
    page_rgbs: list[np.ndarray],
    plan: StorybookPlan,
    output_path: str | Path,
    *,
    width: int,
    height: int,
    fps: int,
    live_draw: bool = False,
) -> dict[str, Any]:
    """Write pages (optional live paint reveal) + crossfades into one MP4."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, float(fps), (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter failed: {output_path}")

    # Live-draw starts on cream paper — any dissolve into page-N head flashes blank.
    # Hard cut keeps the pen reveal intact; Ken Burns path keeps planned crossfade.
    if live_draw:
        xfade_sec = 0.0
    else:
        xfade_sec = float(plan.crossfade_sec)
    xfade_n = max(0, int(round(xfade_sec * float(fps))))
    total = 0
    prev_tail: np.ndarray | None = None

    try:
        for i, page in enumerate(plan.pages):
            rgb = page_rgbs[i]
            seq = _page_frame_sequence(
                rgb,
                hold_sec=page.hold_sec,
                camera=page.camera,
                shot=getattr(page, "shot", "wide"),
                fps=fps,
                width=width,
                height=height,
                live_draw=live_draw,
                visual_action=getattr(page, "visual_action", "") or "",
            )
            if prev_tail is not None and xfade_n > 0 and seq:
                # Crossfade: blend prev last frame into first frames of this page
                head = seq[:xfade_n]
                for k, fr in enumerate(head):
                    u = _smootherstep((k + 1) / float(xfade_n))
                    blended = (
                        prev_tail.astype(np.float32) * (1.0 - u)
                        + fr.astype(np.float32) * u
                    )
                    bgr = cv2.cvtColor(
                        np.clip(blended, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR
                    )
                    writer.write(bgr)
                    total += 1
                seq = seq[xfade_n:]
            for fr in seq:
                writer.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
                total += 1
            prev_tail = seq[-1] if seq else prev_tail
            if prev_tail is None and page_rgbs:
                prev_tail = ken_burns_frame(
                    rgb,
                    t_norm=1.0,
                    camera=page.camera,
                    width=width,
                    height=height,
                    shot=getattr(page, "shot", "wide"),
                )
    finally:
        writer.release()

    return {
        "n_frames": total,
        "fps": fps,
        "duration_sec": total / float(max(1, fps)),
        "path": str(output_path),
        "live_draw": bool(live_draw),
        "engine": "storybook_live_draw" if live_draw else "storybook_kenburns",
    }


def render_storybook(
    plan: StorybookPlan,
    output_dir: str | Path,
    *,
    still_paths: list[Path] | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    mock: bool = True,
    generate_fn: GenerateStillFn | None = None,
    max_page_retries: int = 2,
    still_backend: str | None = None,
    live_draw: bool = False,
) -> dict[str, Any]:
    """
    End-to-end storybook render with character sheet + border QC retries.

    ``still_paths`` injects pre-made page PNGs (tests / recompose).
    ``live_draw`` paints each page on-screen (ink → color) before settle.
    """
    from io import BytesIO

    from libraries.storybook_page_qc import page_fails_fullbleed_qc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    backend_choice = _resolve_still_backend(still_backend) if not mock else "paint"

    (output_dir / "storybook_plan.json").write_text(
        plan.model_dump_json(indent=2), encoding="utf-8"
    )

    page_rgbs: list[np.ndarray] = []
    backends: list[str] = []
    saved: list[str] = []
    qc_rejects = 0
    character_sheet_bytes: bytes | None = None
    character_sheet_path: str | None = None

    # P0: lock character once, reuse as reference for every page.
    if still_paths is None and generate_fn is None and not mock:
        sheet_prompt = getattr(plan, "character_sheet_prompt", "") or ""
        if sheet_prompt:
            sheet_im, sheet_backend = resolve_page_still(
                sheet_prompt,
                width=width,
                height=height,
                index=0,
                mock=mock,
                generate_fn=None,
                still_backend=backend_choice,
            )
            sheet_file = pages_dir / "character_sheet.png"
            sheet_im.save(sheet_file)
            buf = BytesIO()
            sheet_im.save(buf, format="PNG")
            character_sheet_bytes = buf.getvalue()
            character_sheet_path = str(sheet_file)
            backends.append(f"sheet:{sheet_backend}")

    prev_page_bytes: bytes | None = None
    for i, page in enumerate(plan.pages):
        if still_paths is not None and i < len(still_paths):
            im = Image.open(still_paths[i]).convert("RGB").resize(
                (width, height), Image.Resampling.LANCZOS
            )
            backend = "inject"
        else:
            refs: list[bytes] = []
            if character_sheet_bytes:
                refs.append(character_sheet_bytes)
            if prev_page_bytes:
                refs.append(prev_page_bytes)
            im, backend = resolve_page_still(
                page.still_prompt,
                width=width,
                height=height,
                index=i,
                mock=mock,
                generate_fn=generate_fn,
                reference_images=refs or None,
                still_backend=backend_choice,
            )
            # Dark frame / light mat reject → regenerate with full-bleed reminder.
            attempts = 0
            while (
                not mock
                and generate_fn is None
                and page_fails_fullbleed_qc(im)
                and attempts < max(0, int(max_page_retries))
            ):
                qc_rejects += 1
                attempts += 1
                retry_prompt = (
                    page.still_prompt
                    + " RETRY: fill the entire 16:9 frame edge-to-edge; "
                    "delete any border, frame, mat, beige card, oval vignette."
                )
                im, backend = resolve_page_still(
                    retry_prompt,
                    width=width,
                    height=height,
                    index=i,
                    mock=mock,
                    generate_fn=generate_fn,
                    reference_images=refs or None,
                    still_backend=backend_choice,
                )
                backend = f"{backend}+retry{attempts}"
        path = pages_dir / f"page_{i:02d}.png"
        im.save(path)
        page_rgbs.append(np.asarray(im, dtype=np.uint8))
        backends.append(backend)
        saved.append(str(path))
        buf = BytesIO()
        im.save(buf, format="PNG")
        prev_page_bytes = buf.getvalue()

    final = output_dir / "final.mp4"
    compose = compose_storybook_mp4(
        page_rgbs,
        plan,
        final,
        width=width,
        height=height,
        fps=fps,
        live_draw=bool(live_draw),
    )
    report = {
        "ok": final.is_file(),
        "engine": "storybook",
        "schema_version": plan.schema_version,
        "title": plan.title,
        "final_mp4": str(final),
        "n_pages": len(plan.pages),
        "page_stills": saved,
        "still_backends": backends,
        "compose": compose,
        "crossfade_sec": plan.crossfade_sec,
        "character_sheet": character_sheet_path,
        "qc_border_rejects": qc_rejects,
        "style_lock": getattr(plan, "style_lock", None),
        "still_backend": backend_choice,
        "live_draw": bool(live_draw),
        "profile": {"width": width, "height": height, "fps": fps},
    }
    (output_dir / "unified_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report
