"""
Light CPU slideshow renderer for Story drafts.

Splits a brief into title cards, writes PNGs, encodes MP4 via FFmpeg.
Pro path uses Remotion — this is the fast draft fallback only.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Sequence


def _deterministic_slides() -> bool:
    """Stable PNG goldens — skip host TrueType fonts when set."""
    return os.environ.get("ANIMATION_DETERMINISTIC_SLIDES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _split_slides(brief: str, *, max_slides: int = 48) -> list[str]:
    """Split beats; default 48 aligns with ``chapter_tools.max_chapters``."""
    text = (brief or "").strip()
    if not text:
        return ["Untitled"]
    # Prefer blank-line paragraphs, then sentences.
    parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(parts) < 2:
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not parts:
        parts = [text]
    return parts[:max_slides]


def _paste_user_image(
    canvas: Any,
    image_path: Path | str,
    *,
    panel: tuple[int, int, int, int],
) -> None:
    """Cover-fit user image into ``panel`` (left, top, right, bottom)."""
    from PIL import Image

    left, top, right, bottom = panel
    pw, ph = max(1, right - left), max(1, bottom - top)
    try:
        src = Image.open(image_path).convert("RGB")
    except OSError:
        return
    sw, sh = src.size
    scale = max(pw / max(1, sw), ph / max(1, sh))
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    src = src.resize((nw, nh), resample)
    x0 = (nw - pw) // 2
    y0 = (nh - ph) // 2
    src = src.crop((x0, y0, x0 + pw, y0 + ph))
    canvas.paste(src, (left, top))


def _draw_card(
    path: Path,
    *,
    title: str,
    body: str,
    resolution: tuple[int, int],
    accent: tuple[int, int, int],
    image_path: Path | str | None = None,
) -> None:
    """
    Draw a title card. When ``image_path`` is set, text stays on the left
    and the user photo fills the right panel (Path A).
    """
    from PIL import Image, ImageDraw, ImageFont

    w, h = resolution
    img = Image.new("RGB", (w, h), (18, 20, 28))
    draw = ImageDraw.Draw(img)
    # Accent bar
    draw.rectangle([0, 0, w, 12], fill=accent)
    draw.rectangle([0, h - 12, w, h], fill=accent)

    has_image = bool(image_path and Path(image_path).is_file())
    text_right = int(w * 0.52) if has_image else w
    if has_image:
        panel = (int(w * 0.52), 24, w - 16, h - 24)
        _paste_user_image(img, image_path, panel=panel)  # type: ignore[arg-type]
        # Soft divider
        draw.line([(text_right, 28), (text_right, h - 28)], fill=accent, width=2)

    if _deterministic_slides():
        font_title = ImageFont.load_default()
        font_body = font_title
    else:
        try:
            font_title = ImageFont.truetype("arial.ttf", size=max(28, w // 28))
            font_body = ImageFont.truetype("arial.ttf", size=max(20, w // 40))
        except OSError:
            font_title = ImageFont.load_default()
            font_body = font_title

    margin = w // 12
    wrap_title = 18 if has_image else 36
    wrap_body = 22 if has_image else 48
    y = h // 6
    for line in textwrap.wrap(title, width=wrap_title)[:3]:
        draw.text((margin, y), line, fill=(245, 245, 245), font=font_title)
        y += int(font_title.size * 1.35) if hasattr(font_title, "size") else 36

    y += 24
    for line in textwrap.wrap(body, width=wrap_body)[:10]:
        draw.text((margin, y), line, fill=(180, 190, 210), font=font_body)
        y += int(getattr(font_body, "size", 22) * 1.4)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def render_slideshow_mp4(
    brief: str,
    out_dir: Path | str,
    *,
    ffmpeg: str,
    resolution: tuple[int, int] = (1280, 720),
    seconds_per_slide: float = 3.0,
    fps: int = 24,
    studio: str = "story",
    title: str | None = None,
    slide_images: Sequence[str | Path] | None = None,
    max_slides: int = 48,
) -> Path:
    """
    Write ``out_dir/render.mp4`` from text slides.

    Optional ``slide_images`` (Path A): user photos paired 1:1 with text beats
    (extra images ignored; missing images fall back to text-only cards).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "slides"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    style_tag = (
        os.environ.get("STORY_SLIDE_STYLE")
        or os.environ.get("COMMERCIAL_SLIDE_STYLE")
        or studio
        or "story"
    ).lower()
    if "noir" in style_tag or "neon" in style_tag:
        accent = (224, 122, 61)
    elif "doc" in style_tag or "corporate" in style_tag:
        accent = (61, 90, 128)
    else:
        accent = (158, 201, 255)  # pastel narrative default
    slides = _split_slides(brief, max_slides=max_slides)
    header = title or "Story"
    images = [Path(p) for p in (slide_images or []) if p and Path(p).is_file()]

    for i, slide in enumerate(slides):
        img_path = images[i] if i < len(images) else None
        lines = [ln.strip() for ln in slide.splitlines() if ln.strip()]
        if len(lines) >= 2 and not title:
            beat_title = f"{lines[0][:40]} · {i + 1}/{len(slides)}"
            body_text = "\n".join(lines[1:])
        else:
            beat_title = f"{header} · {i + 1}/{len(slides)}"
            body_text = slide
        _draw_card(
            frames_dir / f"slide_{i:03d}.png",
            title=beat_title,
            body=body_text,
            resolution=resolution,
            accent=accent,
            image_path=img_path,
        )

    # Duplicate last frame slightly for encoder safety
    last = frames_dir / f"slide_{len(slides) - 1:03d}.png"
    if last.is_file():
        shutil.copy2(last, frames_dir / f"slide_{len(slides):03d}.png")

    mp4 = out / "render.mp4"
    # -framerate for input images; duration via -r and concat length
    # Use pattern + force duration with tpad-like approach: set input framerate
    # so each image lasts seconds_per_slide.
    input_fps = 1.0 / max(0.5, seconds_per_slide)
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(input_fps),
        "-i",
        str(frames_dir / "slide_%03d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not mp4.is_file() or mp4.stat().st_size <= 0:
        raise RuntimeError(
            "Light slideshow FFmpeg failed:\n"
            + (proc.stderr or proc.stdout or "unknown error")[-2000:]
        )
    return mp4.resolve()


def render_from_prompt(
    brief: str,
    out_dir: Path | str,
    *,
    ffmpeg: str,
    quality: str = "light",
    studio: str = "story",
    slide_images: Sequence[str | Path] | None = None,
) -> dict[str, object]:
    try:
        from tools.render_profiles import get_render_profile, write_render_profile
    except ImportError:
        from ..tools.render_profiles import get_render_profile, write_render_profile

    profile = get_render_profile("studio_story", quality)
    studio = "story"
    write_render_profile(out_dir, profile, extra={"path": "light_slideshow"})
    path = render_slideshow_mp4(
        brief,
        out_dir,
        ffmpeg=ffmpeg,
        resolution=profile.resolution,
        seconds_per_slide=profile.seconds_per_slide,
        fps=profile.fps,
        studio=studio,
        slide_images=slide_images,
    )
    return {
        "render_mp4": str(path),
        "backend": "light_slideshow",
        "resolution": profile.resolution,
        "profile": profile.to_dict(),
        "user_slide_images": len(list(slide_images or [])),
    }
