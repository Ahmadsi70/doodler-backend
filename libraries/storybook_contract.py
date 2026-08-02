"""
Storybook contract — page-by-page silent film (no cutouts).

Why: each page is concept-directed (emotion, angle, staging, visual hook) so
meaning reads at first glance; then Ken Burns + crossfade carry the silent film.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

STORYBOOK_SCHEMA = "storybook_v1"

CameraMove = Literal[
    "subtle_zoom_in", "slow_pan_left", "slow_pan_right", "static"
]
ShotSize = Literal["wide", "medium", "close"]
CameraAngle = Literal["eye_level", "low_angle", "high_angle", "over_shoulder"]


class StorybookPage(BaseModel):
    """One illustrated page directed for first-glance meaning."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    visual_action: str = Field(..., min_length=1)
    hold_sec: float = Field(..., gt=0.0, le=120.0)
    camera: CameraMove = "subtle_zoom_in"
    shot: ShotSize = "wide"
    mood: str = Field("calm", min_length=1)
    # Concept directing — foundation of silent readability.
    concept: str = Field("story beat", min_length=1)
    emotion: str = Field("calm", min_length=1)
    camera_angle: CameraAngle = "eye_level"
    staging: str = Field("hero readable in midground", min_length=1)
    visual_hook: str = Field("clear focal hero", min_length=1)
    narration: str = Field(
        "",
        description="Optional spoken line for educational layered delivery.",
    )
    narration_en: str = Field(
        "",
        description="Optional Latin/offline TTS line when Persian neural TTS is unavailable.",
    )
    still_prompt: str = Field(..., min_length=8)


class StorybookPlan(BaseModel):
    """Full storybook plan before any still is generated."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = STORYBOOK_SCHEMA
    engine: Literal["storybook"] = "storybook"
    title: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    language: str = Field("en", min_length=2, max_length=8)
    target_sec: float = Field(..., gt=0.0, le=600.0)
    crossfade_sec: float = Field(0.9, ge=0.0, le=3.0)
    pages: list[StorybookPage] = Field(default_factory=list)
    global_ambiance: str = Field(
        "soft cinematic daylight, calm colorful storybook painting",
        min_length=1,
    )
    style_lock: str = Field(..., min_length=8)
    character_bible: str = Field(..., min_length=8)
    character_sheet_prompt: str = Field(..., min_length=8)

    @field_validator("schema_version")
    @classmethod
    def _schema_ok(cls, v: str) -> str:
        if v != STORYBOOK_SCHEMA:
            raise ValueError(f"unsupported schema_version: {v}")
        return v
