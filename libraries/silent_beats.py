"""
Silent beat primitives shared by storybook page planning.

Why: storybook needs clause→hold→camera without the old cutout cast contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CameraHint = Literal[
    "subtle_zoom_in",
    "slow_pan_left",
    "slow_pan_right",
    "static",
]


class NarrativeBeat(BaseModel):
    """One silent visual beat — action only, never spoken lines."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    visual_action: str = Field(..., min_length=1)
    hold_sec: float = Field(..., gt=0.0, le=120.0)
    camera_hint: CameraHint = "subtle_zoom_in"
    mood: str = Field("calm", min_length=1)
    dialogue: str = Field(
        "",
        description="Must stay empty for silent narrative delivery.",
    )

    @field_validator("dialogue")
    @classmethod
    def _no_dialogue(cls, v: str) -> str:
        if (v or "").strip():
            raise ValueError("silent narrative forbids dialogue on beats")
        return ""
