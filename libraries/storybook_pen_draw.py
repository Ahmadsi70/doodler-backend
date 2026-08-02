"""
Live paint reveal for storybook stills (Inkplainer-style, headless).

Why: finished Flux/Gemini pages must 'draw themselves' in the film —
ink strokes, then color wash — so the video feels alive, not a slideshow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


def _ordered_edge_points(edge: np.ndarray, *, stride: int = 2) -> list[tuple[int, int]]:
    """Collect edge pixels in a top→right→bottom→left pass (drawing-like)."""
    h, w = edge.shape[:2]
    pts: list[tuple[int, int]] = []
    for x in range(0, w, max(1, stride)):
        col = np.where(edge[:, x] > 0)[0]
        if col.size:
            pts.append((x, int(col[0])))
    for y in range(0, h, max(1, stride)):
        row = np.where(edge[y, :] > 0)[0]
        if row.size:
            pts.append((int(row[-1]), y))
    for x in range(w - 1, -1, -max(1, stride)):
        col = np.where(edge[:, x] > 0)[0]
        if col.size:
            pts.append((x, int(col[-1])))
    for y in range(h - 1, -1, -max(1, stride)):
        row = np.where(edge[y, :] > 0)[0]
        if row.size:
            pts.append((int(row[0]), y))
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for p in pts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _edge_points(rgb: np.ndarray) -> list[tuple[int, int]]:
    """
    Prefer real contour chains (shape outlines) over border extrema.

    Why: top/right/bottom/left sampling looked like a stippled frame, not a
    living brush following the fox/trees.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 140)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    max_pts = 9000 if max(rgb.shape[:2]) >= 900 else 4000
    pts: list[tuple[int, int]] = []
    for c in contours[:48]:
        if len(c) < 16:
            continue
        step = max(1, len(c) // 500)
        for p in c[::step]:
            pts.append((int(p[0][0]), int(p[0][1])))
            if len(pts) >= max_pts:
                return pts
    if len(pts) >= 64:
        return pts
    # Fallback: silhouette walk when Canny is weak.
    stride = 2 if max(rgb.shape[:2]) < 900 else 3
    return _ordered_edge_points(edges, stride=stride)


def scenario_focus_terms(visual_action: str) -> list[str]:
    """
    Ordered story details to reveal for a beat.

    Why: viewers should see hero/prop/detail in scenario order, not random edges.
    """
    low = (visual_action or "").lower()
    fa = visual_action or ""
    order: list[str] = []

    def add(key: str) -> None:
        if key not in order:
            order.append(key)

    # Storybook always leads with the hero, then beat-specific details.
    add("hero")
    if any(w in low for w in ("lantern", "فانوس")) or "blue glass" in low:
        add("lantern")
    if any(w in low for w in ("firefl", "کرم", "spark")):
        add("fireflies")
    if any(w in low for w in ("bridge", "پل")):
        add("bridge")
    if any(w in low for w in ("mist", "fog", "مه")):
        add("mist")
    if any(w in low for w in ("star", "moon", "hill", "تپه", "ستار", "ماه")):
        add("sky")
    add("background")
    add("rest")
    _ = fa
    return order


def _hsv_masks(rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Cheap concept masks from color (no SAM) for scenario-ordered paint."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    masks: dict[str, np.ndarray] = {}
    # Orange / warm fox fur
    masks["hero"] = ((h <= 25) | (h >= 160)) & (s > 60) & (v > 60)
    # Cool cyan / blue lantern glow
    masks["lantern"] = (h >= 85) & (h <= 115) & (s > 50) & (v > 90)
    # Soft yellow firefly sparks
    masks["fireflies"] = (h >= 20) & (h <= 40) & (s > 80) & (v > 160)
    # Cool mist / pale blues-greys
    masks["mist"] = (s < 45) & (v > 140) & (h >= 80) & (h <= 140)
    # Sky / night upper band (desaturated upper third or star-ish)
    hh, ww = rgb.shape[:2]
    upper = np.zeros((hh, ww), dtype=bool)
    upper[: max(1, hh // 3), :] = True
    masks["sky"] = upper & (v > 40) & (s < 90)
    # Bridge-ish mid-brown structures
    masks["bridge"] = (h >= 8) & (h <= 25) & (s > 40) & (s < 140) & (v > 40) & (v < 160)
    # Deep teal / forest background
    masks["background"] = (h >= 70) & (h <= 100) & (s > 40) & (v < 140)
    return masks


def _scenario_priority_map(
    rgb: np.ndarray,
    visual_action: str,
) -> np.ndarray:
    """
    Float map in [0,1]: lower = drawn earlier (scenario-first).

    Combines concept color masks with contour stroke order.
    """
    h, w = rgb.shape[:2]
    terms = scenario_focus_terms(visual_action)
    masks = _hsv_masks(rgb)
    # Start late; pull forward pixels belonging to earlier scenario terms.
    prio = np.full((h, w), 0.92, dtype=np.float32)
    n_terms = max(1, len(terms))
    for i, term in enumerate(terms):
        m = masks.get(term)
        if m is None or not np.any(m):
            continue
        # Morphological clean so small noise doesn't steal the brush.
        m_u8 = (m.astype(np.uint8)) * 255
        m_u8 = cv2.morphologyEx(m_u8, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m_u8 = cv2.dilate(m_u8, np.ones((5, 5), np.uint8), iterations=1)
        base = i / float(n_terms)
        # Within a term, slightly earlier near term centroid (focus read).
        ys, xs = np.where(m_u8 > 0)
        if ys.size == 0:
            continue
        cy, cx = float(ys.mean()), float(xs.mean())
        yy, xx = np.mgrid[0:h, 0:w]
        dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        dnorm = dist / float(max(h, w))
        local = base + 0.08 * dnorm
        prio = np.where(m_u8 > 0, np.minimum(prio, local.astype(np.float32)), prio)

    # Contour boost: edges inside early regions get a tiny head-start.
    pts = _edge_points(rgb)
    brush = max(2, min(w, h) // 160)
    order = _stroke_order_map((h, w), pts, brush=brush)
    if order.any():
        omax = float(order.max())
        stroke_t = np.where(order > 0, order.astype(np.float32) / omax, 1.0)
        prio = 0.72 * prio + 0.28 * stroke_t.astype(np.float32)
    return np.clip(prio, 0.0, 1.0)


def _stroke_order_map(
    shape: tuple[int, int],
    pts: list[tuple[int, int]],
    *,
    brush: int,
) -> np.ndarray:
    """
    Per-pixel 1-based stroke order (0 = blank). Earliest stamp wins.

    Why: O(1) frame lookup instead of redrawing circles every frame.
    """
    h, w = shape
    order = np.zeros((h, w), dtype=np.int32)
    if not pts:
        return order
    stamp = np.zeros((h, w), dtype=np.uint8)
    for i, (x, y) in enumerate(pts):
        stamp[:] = 0
        cv2.circle(stamp, (x, y), brush, 1, -1)
        hit = stamp > 0
        virgin = order == 0
        order[hit & virgin] = i + 1
    # Soft thicken: dilate nonzero labels without inventing new late strokes.
    if order.any():
        kernel = np.ones((3, 3), np.uint8)
        nonzero = (order > 0).astype(np.uint8)
        grown = cv2.dilate(nonzero, kernel, iterations=1)
        # Fill new rim with nearest existing order via dilate on float proxy
        prox = order.astype(np.float32)
        prox[order == 0] = 1e9
        for _ in range(1):
            prox = cv2.erode(prox, kernel)  # min filter = earliest neighbor
        order = np.where((order == 0) & (grown > 0), prox.astype(np.int32), order)
        order[order >= int(1e8)] = 0
    return order


def _contour_polylines(rgb: np.ndarray) -> list[np.ndarray]:
    """Return contour polylines (Nx2 int) largest-first."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 55, 130)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    polys: list[np.ndarray] = []
    for c in contours[:60]:
        if len(c) < 20:
            continue
        pts = c.reshape(-1, 2).astype(np.int32)
        polys.append(pts)
    return polys


def _color_pen_samples(
    rgb: np.ndarray,
    visual_action: str,
    *,
    max_samples: int = 5500,
) -> list[tuple[int, int]]:
    """
    Ordered tip samples: scenario-important contours first, along-path order.

    Why: feels like a live colorful pen, not a region flood wipe.
    """
    h, w = rgb.shape[:2]
    prio = _scenario_priority_map(rgb, visual_action)
    polys = _contour_polylines(rgb)
    if not polys:
        pts = _edge_points(rgb)
        return pts[:max_samples]

    scored: list[tuple[float, np.ndarray]] = []
    for poly in polys:
        xs = np.clip(poly[:, 0], 0, w - 1)
        ys = np.clip(poly[:, 1], 0, h - 1)
        score = float(prio[ys, xs].mean())
        scored.append((score, poly))
    scored.sort(key=lambda t: t[0])

    samples: list[tuple[int, int]] = []
    for _, poly in scored:
        step = max(1, len(poly) // 420)
        for x, y in poly[::step]:
            samples.append((int(x), int(y)))
            if len(samples) >= max_samples:
                return samples
    if len(samples) < 64:
        samples.extend(_edge_points(rgb))
    return samples[:max_samples]


def _pen_time_map(
    shape: tuple[int, int],
    samples: list[tuple[int, int]],
    *,
    brush: int,
) -> np.ndarray:
    """Per-pixel first touch time in [0,1]; inf = never touched by the pen tip."""
    h, w = shape
    tmap = np.full((h, w), np.inf, dtype=np.float32)
    if not samples:
        return tmap
    n = float(len(samples))
    stamp = np.zeros((h, w), dtype=np.uint8)
    for i, (x, y) in enumerate(samples):
        stamp[:] = 0
        cv2.circle(stamp, (x, y), brush, 1, -1)
        # Mild elongation along next tip for stroke continuity.
        if i + 1 < len(samples):
            x2, y2 = samples[i + 1]
            cv2.line(stamp, (x, y), (x2, y2), 1, max(1, brush))
        hit = stamp > 0
        virgin = ~np.isfinite(tmap)
        tmap[hit & virgin] = float(i / n)
    # Soft thicken earliest times.
    finite = np.isfinite(tmap).astype(np.uint8)
    if finite.any():
        grown = cv2.dilate(finite, np.ones((3, 3), np.uint8), iterations=1)
        prox = tmap.copy()
        prox[~np.isfinite(prox)] = 1e9
        prox = cv2.erode(prox, np.ones((3, 3), np.uint8))
        fill = (tmap == np.inf) & (grown > 0)
        tmap = np.where(fill, prox, tmap)
        tmap[tmap >= 1e8] = np.inf
    return tmap


def pen_draw_frame_sequence(
    rgb: np.ndarray,
    *,
    n_frames: int,
    draw_frac: float = 0.55,
    fill_frac: float = 0.38,
    ink_rgb: tuple[int, int, int] = (35, 32, 40),
    paper_rgb: tuple[int, int, int] = (248, 244, 236),
    color_strokes: bool = True,
    visual_action: str = "",
) -> list[np.ndarray]:
    """
    Live colorful pen: tip follows contours, painting source colors onto paper.

    Timeline (normalized t in [0,1]):
    - [0, draw_frac): colored pen strokes (scenario-ordered)
    - [draw_frac, draw_frac+fill_frac): watercolor wash fills remaining areas
    - remainder: finished painting
    """
    src = np.asarray(rgb, dtype=np.uint8)
    if src.ndim != 3:
        raise ValueError("rgb must be HxWx3")
    h, w = src.shape[:2]
    n = max(1, int(n_frames))

    # Fat colorful brush — reads as paint pen, not hairline ink.
    brush = max(3, min(w, h) // 95)
    samples = _color_pen_samples(src, visual_action)
    tmap = _pen_time_map((h, w), samples, brush=brush)

    painted_seed = np.isfinite(tmap).astype(np.uint8) * 255
    if painted_seed.any():
        dist = cv2.distanceTransform(
            cv2.bitwise_not(painted_seed), cv2.DIST_L2, 5
        ).astype(np.float32)
        max_dist = float(dist.max()) or 1.0
    else:
        dist = np.zeros((h, w), dtype=np.float32)
        max_dist = 1.0

    paper = np.empty((h, w, 3), dtype=np.uint8)
    paper[:, :] = paper_rgb
    tip_dark = np.array(ink_rgb, dtype=np.uint8)
    frames: list[np.ndarray] = []

    draw_end = float(np.clip(draw_frac, 0.08, 0.9))
    fill_end = float(np.clip(draw_end + fill_frac, draw_end + 0.05, 0.99))

    for i in range(n):
        t = 0.0 if n == 1 else i / float(n - 1)
        if t < draw_end:
            u = t / max(1e-6, draw_end)
            # Fast pen, tiny blank head so color starts almost immediately.
            u = 0.06 + 0.94 * (u ** 0.7)
            frame = paper.copy()
            stroke = np.isfinite(tmap) & (tmap <= u)
            if color_strokes:
                # Watercolor bleed from the moving tip into nearby paint.
                if stroke.any():
                    local = stroke.astype(np.uint8) * 255
                    dloc = cv2.distanceTransform(
                        cv2.bitwise_not(local), cv2.DIST_L2, 5
                    )
                    bleed_r = float(brush) * (1.8 + 3.2 * u)
                    bleed = dloc <= bleed_r
                    soft = np.clip((bleed_r + 4.0 - dloc) / 4.0, 0.0, 1.0)
                    soft = np.where(bleed, soft, 0.0).astype(np.float32)
                    soft3 = soft[:, :, None]
                    frame = (
                        paper.astype(np.float32) * (1.0 - soft3)
                        + src.astype(np.float32) * soft3
                    ).astype(np.uint8)
                frame[stroke] = src[stroke]
                # Moving tip: slight dark rim so the pen tip is readable.
                tip = np.isfinite(tmap) & (tmap <= u) & (tmap > max(0.0, u - 0.035))
                if tip.any():
                    frame[tip] = (
                        frame[tip].astype(np.float32) * 0.78
                        + tip_dark.astype(np.float32) * 0.22
                    ).astype(np.uint8)
            else:
                frame[stroke] = tip_dark
        elif t < fill_end:
            u = (t - draw_end) / max(1e-6, fill_end - draw_end)
            u = float(np.clip(u, 0.0, 1.0)) ** 0.6
            # Watercolor wash from pen strokes outward — still colorful source.
            thresh = (0.08 + 0.98 * u) * max_dist
            soft = np.clip((thresh + 14.0 - dist) / 14.0, 0.0, 1.0)
            soft = np.maximum(soft, (np.isfinite(tmap) & (tmap <= 1.0)).astype(np.float32))
            soft3 = soft[:, :, None]
            frame = (
                paper.astype(np.float32) * (1.0 - soft3)
                + src.astype(np.float32) * soft3
            ).astype(np.uint8)
        else:
            frame = src.copy()
        frames.append(frame)
    return frames


def render_pen_draw_mp4(
    still_path: str | Path,
    output_path: str | Path,
    *,
    duration_sec: float = 3.0,
    fps: int = 24,
    width: int | None = None,
    height: int | None = None,
    ink_rgb: tuple[int, int, int] = (25, 25, 30),
    paper_rgb: tuple[int, int, int] = (245, 242, 235),
    draw_frac: float = 0.55,
    fill_frac: float = 0.30,
) -> dict[str, Any]:
    """Render contour ink → color fill → settle on the full still to MP4."""
    still_path = Path(still_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(still_path).convert("RGB")
    if width and height:
        im = im.resize((int(width), int(height)), Image.Resampling.LANCZOS)
    rgb = np.asarray(im, dtype=np.uint8)
    h, w = rgb.shape[:2]
    n = max(1, int(round(float(duration_sec) * float(fps))))
    frames = pen_draw_frame_sequence(
        rgb,
        n_frames=n,
        draw_frac=draw_frac,
        fill_frac=fill_frac,
        ink_rgb=ink_rgb,
        paper_rgb=paper_rgb,
    )

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, float(fps), (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter failed: {output_path}")
    try:
        for frame in frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()

    return {
        "ok": output_path.is_file(),
        "path": str(output_path),
        "n_frames": n,
        "fps": fps,
        "duration_sec": n / float(max(1, fps)),
        "engine": "storybook_pen_draw",
    }
