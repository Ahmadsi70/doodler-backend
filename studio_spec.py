"""
StudioSpec — code-first control plane for Story.

Why: free-text agents alone cannot give a “free studio”. Authors drive shots,
camera, timing, pose, assets, and quality from Python/JSON; agents are optional.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PoseName = Literal["idle", "walk", "react", "run"]
LensName = Literal["standard", "action", "beauty"]
CameraName = Literal["static", "motivated_push", "pan_follow", "reveal_drift"]
ShotSizeName = Literal["WS", "MS", "CU", "insert"]
QualityName = Literal["light", "pro"]
StudioMode = Literal["direct", "agents"]
StoryBeatName = Literal[
    "entrance",
    "reveal",
    "reaction",
    "conflict",
    "decision",
    "quiet_hold",
    "exit",
]


class ShotControl(BaseModel):
    """One fully specified narrative shot (code-controlled)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: str = Field(min_length=1)
    title: str = ""
    duration_sec: float = Field(default=3.0, gt=0, le=120)
    lens: LensName = "standard"
    camera: CameraName = "static"
    shot_size: ShotSizeName = "MS"
    composition: Literal["L", "C", "R"] = "C"
    pose: PoseName = "idle"
    expression: str = "neutral"
    story_beat: StoryBeatName = "decision"
    anticipation_frames: int = Field(default=6, ge=0, le=48)
    hold_frames: int = Field(default=12, ge=0, le=96)
    lighting: str = "three_point"
    look_space: Literal["left", "right", "none", ""] = ""
    notes: str = ""
    dialogue: str = ""
    """Optional VO / spoken line for PhonemeSyncAgent (lip-sync)."""
    vo_path: str = ""
    """Optional path to spoken wav; PhonemeSync stretches to real duration."""


class CharacterLayers(BaseModel):
    """Optional layered character sheets (same identity, separate parts)."""

    model_config = ConfigDict(extra="forbid")

    body: str | None = None
    head: str | None = None
    hand: str | None = None


class StudioAssets(BaseModel):
    """User media referenced by absolute/relative paths."""

    model_config = ConfigDict(extra="forbid")

    character_path: str | None = None
    slide_images: list[str] = Field(default_factory=list)
    layers: CharacterLayers = Field(default_factory=CharacterLayers)


class StudioSpec(BaseModel):
    """
    Single Information Point that owns the render.

    ``mode=direct``: shots from this spec only (agents skipped).
    ``mode=agents``: brief synthesized from shots, then optional agent/LLM enrich.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0.0"] = "1.0.0"
    title: str = "Story"
    quality: QualityName = "light"
    mode: StudioMode = "direct"
    runtime_seconds: float = Field(default=30.0, gt=0, le=600)
    style_id: str = "symmetrical_pastel_cinema"
    grade: str = "pastel_muted"
    pace: str = "measured"
    emotion: str = "neutral"
    use_llm: bool = False
    use_agents: bool = False
    max_revision_passes: int = Field(default=0, ge=0, le=3)
    character_path: str | None = None
    character_id: str | None = None
    """Library id from ``.story/characters/<id>`` — resolved when path is empty."""
    assets: StudioAssets = Field(default_factory=StudioAssets)
    shots: list[ShotControl] = Field(min_length=1)
    seed: int | None = None
    notes: str = ""

    @field_validator("shots")
    @classmethod
    def _need_shots(cls, v: list[ShotControl]) -> list[ShotControl]:
        if not v:
            raise ValueError("StudioSpec.shots must be non-empty")
        return v

    def resolved_character(self) -> str | None:
        path = self.character_path or (self.assets.character_path if self.assets else None)
        if path:
            return path
        if self.character_id:
            try:
                from tools.character_library import resolve_character

                return resolve_character(self.character_id)["character_path"]
            except Exception:  # noqa: BLE001
                return None
        return None

    def resolved_appearance_fa(self) -> str:
        """Appearance lock text from library profile when character_id is set."""
        if not self.character_id:
            return ""
        try:
            from tools.character_library import get_character

            prof = get_character(self.character_id)
            return str((prof or {}).get("appearance_fa") or "")
        except Exception:  # noqa: BLE001
            return ""

    def to_brief(self) -> str:
        """Synthesize a blank-line brief when agent mode is requested."""
        parts = []
        for i, sh in enumerate(self.shots):
            title = sh.title or f"Shot {i}"
            parts.append(f"{title}\n{sh.action}")
        return "\n\n".join(parts)

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
