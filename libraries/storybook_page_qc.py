"""
Storybook page QC — reject framed / matted stills before compose.

Why: Gemini/Flux often return oval mats or dark proscenium borders that pop in
Ken Burns and tank critique scores. Light beige mats need the same gate.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _luma_border_center(
    image: Image.Image | np.ndarray,
    *,
    border_frac: float,
) -> tuple[float, float] | None:
    arr = np.asarray(
        image.convert("RGB") if isinstance(image, Image.Image) else image,
        dtype=np.float32,
    )
    if arr.ndim != 3 or arr.shape[0] < 32 or arr.shape[1] < 32:
        return None
    h, w = arr.shape[:2]
    t = max(2, int(round(min(h, w) * float(border_frac))))
    lum = arr.mean(axis=2)
    border = np.concatenate(
        [
            lum[:t, :].ravel(),
            lum[-t:, :].ravel(),
            lum[:, :t].ravel(),
            lum[:, -t:].ravel(),
        ]
    )
    center = lum[t : h - t, t : w - t]
    if center.size == 0:
        return None
    return float(border.mean()), float(center.mean())


def page_has_border_frame(
    image: Image.Image | np.ndarray,
    *,
    border_frac: float = 0.06,
    dark_mean: float = 45.0,
    center_delta: float = 35.0,
) -> bool:
    """
    True when a dark frame surrounds a brighter interior.

    Why: full-bleed pages should not have picture-frame / stage borders.
    """
    stats = _luma_border_center(image, border_frac=border_frac)
    if stats is None:
        return False
    b_mean, c_mean = stats
    return b_mean < float(dark_mean) and (c_mean - b_mean) >= float(center_delta)


def page_has_light_mat(
    image: Image.Image | np.ndarray,
    *,
    border_frac: float = 0.06,
    light_mean: float = 200.0,
    center_delta: float = 40.0,
) -> bool:
    """
    True when a bright beige/cream mat surrounds a darker painting.

    Why: kids-book generators often wrap scenes in oval/card mats.
    """
    stats = _luma_border_center(image, border_frac=border_frac)
    if stats is None:
        return False
    b_mean, c_mean = stats
    return b_mean > float(light_mean) and (b_mean - c_mean) >= float(center_delta)


def page_fails_fullbleed_qc(image: Image.Image | np.ndarray) -> bool:
    """True when any mat/frame detector rejects the still."""
    return page_has_border_frame(image) or page_has_light_mat(image)
