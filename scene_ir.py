"""
Scene IR — Frozen single source of truth for the multi-agent animation system.

Williams (Animator's Survival Kit) + Glebas (Directing the Story).
All agents read/write these Pydantic v2 models. Frame arithmetic belongs in
deterministic tools; agents never invent FPS other than UNIVERSAL_FPS.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Constants ───────────────────────────────────────────────────────────────

UNIVERSAL_FPS: Literal[24] = 24
"""Williams Universal Constant — never override."""


class FrozenModel(BaseModel):
    """Base for all Scene IR models — strict, immutable-friendly."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


# ── Shared geometry / timing primitives ─────────────────────────────────────


class Vec2(FrozenModel):
    x: float = 0.0
    y: float = 0.0


class Vec3(FrozenModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class BoundingBox2D(FrozenModel):
    """Axis-aligned screen or local bounds (normalized 0..1 unless noted)."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    space: Literal["normalized", "pixels", "world"] = "normalized"

    @model_validator(mode="after")
    def _ordered(self) -> BoundingBox2D:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError("BoundingBox2D max_* must be >= min_*")
        return self


class FrameRange(FrozenModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)

    @model_validator(mode="after")
    def _range_ok(self) -> FrameRange:
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must be >= start_frame")
        return self


# ── StoryBrief ──────────────────────────────────────────────────────────────


class CastMember(FrozenModel):
    id: str
    name: str
    species: Literal["human", "dog", "cat", "horse", "creature", "prop"] = "human"
    role: str = "protagonist"
    notes: str = ""


class StoryBeat(FrozenModel):
    id: str
    order: int = Field(ge=0)
    summary: str
    emotional_intent: str = ""
    must_hit: bool = True


class StoryBrief(FrozenModel):
    """Manager ingest — plain-text story → structured brief."""

    title: str = "Untitled"
    user_prompt: str
    logline: str = ""
    tone: str = ""
    runtime_seconds_budget: float = Field(default=30.0, gt=0)
    fps: Literal[24] = UNIVERSAL_FPS
    cast: list[CastMember] = Field(default_factory=list)
    beats: list[StoryBeat] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("fps")
    @classmethod
    def _fps_locked(cls, v: int) -> int:
        if v != UNIVERSAL_FPS:
            raise ValueError(f"fps must be {UNIVERSAL_FPS} (Williams Universal Constant)")
        return v


# ── SceneSequence ───────────────────────────────────────────────────────────


class MotivationMode(str, Enum):
    REACTION = "reaction"
    ACTION = "action"


class JourneyStage(str, Enum):
    ORDINARY_WORLD = "ordinaryWorld"
    CALL_TO_ADVENTURE = "callToAdventure"
    REFUSAL = "refusal"
    MEETING_MENTOR = "meetingMentor"
    CROSSING_THRESHOLD = "crossingThreshold"
    TESTS_ALLIES_ENEMIES = "testsAlliesEnemies"
    APPROACH = "approach"
    ORDEAL = "ordeal"
    REWARD = "reward"
    ROAD_BACK = "roadBack"
    RESURRECTION = "resurrection"
    RETURN_WITH_ELIXIR = "returnWithElixir"


class SceneNode(FrozenModel):
    id: str
    order: int = Field(ge=0)
    title: str
    summary: str
    stakes: float = Field(default=0.1, ge=0.0, le=1.0)
    motivation_mode: MotivationMode = MotivationMode.REACTION
    journey_stage: JourneyStage | None = None
    frame_range: FrameRange | None = None
    notes: str = ""


class SceneSequence(FrozenModel):
    """Macro multi-scene structure (Narrative / Hero Journey)."""

    id: str = "sequence-main"
    scenes: list[SceneNode] = Field(default_factory=list)
    macro_question: str = ""
    dramatic_irony_active: bool = False
    """Hero Journey state machine snapshot (Phase 17)."""
    hero_character_id: str = "walker"
    hero_journey_stage: JourneyStage | None = None
    hero_stakes: float = Field(default=0.1, ge=0.0, le=1.0)
    hero_motivation_mode: MotivationMode = MotivationMode.REACTION
    """Story-delay: frames inserted as obstacles before the goal answer."""
    delay_frames_inserted: int = Field(default=0, ge=0)
    """Pacing punctuation holds/fades after fast action (frame counts)."""
    pacing_punctuation_frames: int = Field(default=0, ge=0)
    notes: str = ""


# ── ShotList ────────────────────────────────────────────────────────────────


class CausalOrigin(FrozenModel):
    shot_id: str
    event_id: str
    kind: Literal["physical", "psychological", "dramatic", "ironic", "thematic"] = (
        "physical"
    )
    label: str = ""


class ShotSpec(FrozenModel):
    id: str
    scene_id: str
    order: int = Field(ge=0)
    label: str
    frame_range: FrameRange
    covers_subject_id: str = ""
    lens: Literal["wide", "normal", "telephoto"] = "normal"
    causal_origin: CausalOrigin
    causal_role: Literal["root", "cause", "effect"] = "effect"
    notes: str = ""


class ShotList(FrozenModel):
    id: str = "shots-main"
    shots: list[ShotSpec] = Field(default_factory=list)
    notes: str = ""


# ── PerformanceTimeline ─────────────────────────────────────────────────────


class PoseKeyframe(FrozenModel):
    frame: int = Field(ge=0)
    subject_id: str
    root: Vec3 = Field(default_factory=Vec3)
    bbox: BoundingBox2D
    phase: str = ""
    mouth_shape: str | None = None
    """Commercial Storyboard — Golden Frame flag for still renders."""
    snapshot_frame: bool = False
    notes: str = ""


class ContactMarker(FrozenModel):
    """Physics / walk / landing Contact — Foley must lock to this frame."""

    id: str
    frame: int = Field(ge=0)
    subject_id: str
    label: str
    kind: Literal["footstep", "impact", "landing", "bounce"] = "impact"


class PhonemeMarker(FrozenModel):
    token: str
    shape: str
    audio_frame: int = Field(ge=0)
    visual_frame: int = Field(ge=0)
    lead_frames: Literal[1, 2] = 2

    @model_validator(mode="after")
    def _visual_leads(self) -> PhonemeMarker:
        if self.visual_frame > self.audio_frame:
            raise ValueError("visual_frame must be <= audio_frame (Williams lip-sync)")
        return self


class PerformanceTimeline(FrozenModel):
    """Performance channels — every keyframe carries frame + bounding box."""

    id: str = "performance-main"
    fps: Literal[24] = UNIVERSAL_FPS
    total_frames: int = Field(default=0, ge=0)
    keyframes: list[PoseKeyframe] = Field(default_factory=list)
    contacts: list[ContactMarker] = Field(default_factory=list)
    phonemes: list[PhonemeMarker] = Field(default_factory=list)
    notes: str = ""

    @field_validator("fps")
    @classmethod
    def _fps_locked(cls, v: int) -> int:
        if v != UNIVERSAL_FPS:
            raise ValueError(f"fps must be {UNIVERSAL_FPS}")
        return v


# ── CameraPlan ──────────────────────────────────────────────────────────────


class CameraKeyframe(FrozenModel):
    frame: int = Field(ge=0)
    position: Vec3
    look_at: Vec3
    lens: Literal["wide", "normal", "telephoto"] = "normal"
    fov_deg: float = Field(default=45.0, gt=0)


class MisdirectionCue(FrozenModel):
    secret_side: Literal["screenLeft", "screenRight"]
    distraction_side: Literal["screenLeft", "screenRight"]
    frame_range: FrameRange
    label: str = ""

    @model_validator(mode="after")
    def _opposite(self) -> MisdirectionCue:
        if self.secret_side == self.distraction_side:
            raise ValueError("distraction must be opposite screen side")
        return self


class CameraPlan(FrozenModel):
    id: str = "camera-main"
    keyframes: list[CameraKeyframe] = Field(default_factory=list)
    locked_action_side: Literal["north", "south"] | None = None
    tracking_subject_id: str | None = None
    misdirection: list[MisdirectionCue] = Field(default_factory=list)
    """Line of Action endpoints (XZ plane) for 180° enforcement."""
    line_point_a: Vec3 | None = None
    line_point_b: Vec3 | None = None
    """Shot / reverse-shot eyelines — must be opposite screen looks."""
    eyeline_a: Literal["screenLeft", "screenRight"] | None = None
    eyeline_b: Literal["screenLeft", "screenRight"] | None = None
    notes: str = ""


# ── CelStack ────────────────────────────────────────────────────────────────


class CelLevel(FrozenModel):
    level: Literal[1, 2, 3, 4, 5]
    id: str
    name: str
    role: Literal[
        "mainCharacter",
        "secondaryCharacter",
        "props",
        "backgroundOverlay",
        "weatherFx",
    ]
    exposure: Literal["Ones", "Twos"] = "Twos"
    frames_per_drawing: int = Field(default=2, ge=1)
    drawings: list[int] = Field(default_factory=list)
    notes: str = ""


class LightSourceIR(FrozenModel):
    role: Literal["key", "fill", "back"]
    direction: Vec3
    intensity: float = Field(ge=0.0, le=1.0)
    softness: float = Field(default=0.5, ge=0.0, le=1.0)


class ThreePointLightingIR(FrozenModel):
    subject_id: str
    key: LightSourceIR
    fill: LightSourceIR
    back: LightSourceIR
    rim_strength: float = Field(ge=0.0, le=1.0)


class MultiplaneLayerIR(FrozenModel):
    plane: Literal["foreground", "midground", "background"]
    depth_z: float = Field(gt=0)
    parallax_factor: float = Field(gt=0)
    gray_min_pct: float = Field(ge=0.0, le=100.0)
    gray_max_pct: float = Field(ge=0.0, le=100.0)
    contrast_span: float = Field(ge=0.0, le=100.0)
    notes: str = ""


class NotanReportIR(FrozenModel):
    """Manager-validated Notan massing metrics (Phase 19)."""

    light_ratio: float = Field(ge=0.0, le=1.0)
    dark_ratio: float = Field(ge=0.0, le=1.0)
    spotty_score: float = Field(ge=0.0, le=1.0)
    harmony_score: float = Field(ge=0.0, le=1.0)
    passes: bool = False
    notes: str = ""


class ProductAssetIR(FrozenModel):
    """Photo plate on a cel (Story: character/prop still; legacy name kept for IR compat)."""

    id: str
    image_path: str
    scale: float = Field(default=1.0, gt=0.0)
    target_cel_level: Literal[1, 2, 3, 4, 5] = 3
    gestalt_focal: Vec3 = Field(default_factory=lambda: Vec3(x=0.0, y=0.0, z=1.0))
    label: str = ""
    notes: str = ""


# Story-facing alias — same schema, clearer intent in narrative pipelines.
CharacterAssetIR = ProductAssetIR


class CelStack(FrozenModel):
    """Williams K.I.S.S. 5-level cels + lighting / multiplane / Notan."""

    id: str = "cel-stack"
    total_frames: int = Field(default=0, ge=0)
    levels: list[CelLevel] = Field(default_factory=list)
    lighting: ThreePointLightingIR | None = None
    multiplane: list[MultiplaneLayerIR] = Field(default_factory=list)
    notan: NotanReportIR | None = None
    design_clarity: float | None = Field(default=None, ge=0.0, le=1.0)
    product_assets: list[ProductAssetIR] = Field(default_factory=list)
    notes: str = ""


class StoryboardSnapshot(FrozenModel):
    """Golden Frame snapshot for Story storyboard / still review."""

    frame: int = Field(ge=0)
    reason: str
    snapshot_frame: Literal[True] = True
    subject_id: str = ""
    shot_id: str | None = None
    png_path: str = ""
    notes: str = ""


class StoryboardPlan(FrozenModel):
    id: str = "storyboard-main"
    snapshots: list[StoryboardSnapshot] = Field(default_factory=list)
    mode: Literal["animation", "storyboard"] = "animation"
    notes: str = ""


class AiImagePrompt(FrozenModel):
    """Diffusion / Midjourney prompt derived from a Golden Frame 3D state."""

    id: str
    frame: int = Field(ge=0)
    prompt: str
    negative_prompt: str = ""
    style_tags: list[str] = Field(default_factory=list)
    snapshot_png: str = ""
    notes: str = ""


# ── FoleyTimeline ───────────────────────────────────────────────────────────


class FoleyCueIR(FrozenModel):
    id: str
    kind: Literal[
        "contactImpact",
        "stallingAnticipation",
        "stallingBrake",
        "punctuation",
    ]
    category: Literal[
        "cartoonSlip",
        "heavyThud",
        "swoosh",
        "boink",
        "brake",
        "footstep",
    ]
    frame: int = Field(ge=0)
    asset_path: str = ""
    contact_id: str | None = None
    noise_filter_applied: bool = True
    label: str = ""
    notes: str = ""


class FoleyTimeline(FrozenModel):
    id: str = "foley-main"
    fps: Literal[24] = UNIVERSAL_FPS
    cues: list[FoleyCueIR] = Field(default_factory=list)
    notes: str = ""


# ── ComplianceReport ────────────────────────────────────────────────────────


class ComplianceViolation(FrozenModel):
    rule_id: str
    severity: Literal["critical", "warning"]
    message: str
    owner_agent: str
    frame: int | None = None
    shot_id: str | None = None


class ComplianceReport(FrozenModel):
    """
    Strict classical-rule checklist. Manager blocks CodeEmitter unless
    `passed` is True (all critical flags True and no critical violations).
    """

    fps_is_24: bool = False
    contact_sounds_match_contact_frames: bool = False
    phoneme_visual_leads_audio: bool = False
    splat_normal_on_contact: bool = False
    line_of_action_ok: bool = False
    eyeline_continuity_ok: bool = False
    notan_clear: bool = False
    design_equation_clarity_ok: bool = False
    all_shots_have_causal_origin: bool = False
    quadruped_hind_offset_ok: bool = False
    cel_levels_isolated: bool = False
    motivation_enforced: bool = False

    violations: list[ComplianceViolation] = Field(default_factory=list)
    revision_target: str | None = None
    notes: str = ""

    @property
    def all_critical_flags_true(self) -> bool:
        return all(
            (
                self.fps_is_24,
                self.contact_sounds_match_contact_frames,
                self.phoneme_visual_leads_audio,
                self.splat_normal_on_contact,
                self.line_of_action_ok,
                self.eyeline_continuity_ok,
                self.notan_clear,
                self.design_equation_clarity_ok,
                self.all_shots_have_causal_origin,
                self.quadruped_hind_offset_ok,
                self.cel_levels_isolated,
                self.motivation_enforced,
            )
        )

    @property
    def has_critical_violations(self) -> bool:
        return any(v.severity == "critical" for v in self.violations)

    @property
    def passed(self) -> bool:
        return self.all_critical_flags_true and not self.has_critical_violations


# ── Composite Scene IR ──────────────────────────────────────────────────────


class AuditorVerdict(FrozenModel):
    """Single specialized auditor score (Score-Revise-Reevaluate)."""

    auditor_id: str
    passed: bool = False
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    revision_target: str | None = None
    findings: list[str] = Field(default_factory=list)
    notes: str = ""


class AuditorPanelReport(FrozenModel):
    """Panel aggregate — CodeEmitter blocked until passed=True."""

    id: str = "auditor-panel"
    verdicts: list[AuditorVerdict] = Field(default_factory=list)
    passed: bool = False
    min_score: float = Field(default=0.70, ge=0.0, le=1.0)
    revision_target: str | None = None
    iteration: int = Field(default=0, ge=0)
    notes: str = ""


class CompressedContextLayer(FrozenModel):
    name: Literal["essential", "relevant", "summary", "collaboration"]
    budget_pct: float = Field(ge=0.0, le=1.0)
    token_budget: int = Field(ge=0)
    token_used: int = Field(ge=0)
    content: str = ""


class CompressedContextPack(FrozenModel):
    """Four-layer AutoWorldBuilder-style context pack under a hard token budget."""

    id: str = "context-pack"
    token_budget: int = Field(default=8000, gt=0)
    token_used: int = Field(default=0, ge=0)
    layers: list[CompressedContextLayer] = Field(default_factory=list)
    query: str = ""
    notes: str = ""


class PipelineStage(str, Enum):
    """Ordered production stages for Manager routing."""

    INIT = "init"
    TIMING = "timing"
    NARRATIVE = "narrative"
    NLP = "nlp"
    CINEMATOGRAPHY = "cinematography"
    SEMIOTICS = "semiotics"
    LOCOMOTION = "locomotion"
    PHYSICS = "physics"
    ACTING = "acting"
    RENDER = "render"
    FOLEY = "foley"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    EMIT = "emit"
    DONE = "done"


class SceneIR(FrozenModel):
    """
    Full frozen IR document passed between Manager and specialists.
    Absent sections are None until the owning agent fills them.
    """

    schema_version: Literal["1.0.0"] = "1.0.0"
    user_prompt: str = ""
    story_brief: StoryBrief | None = None
    scene_sequence: SceneSequence | None = None
    shot_list: ShotList | None = None
    performance: PerformanceTimeline | None = None
    camera_plan: CameraPlan | None = None
    cel_stack: CelStack | None = None
    foley: FoleyTimeline | None = None
    compliance: ComplianceReport | None = None
    storyboard: StoryboardPlan | None = None
    ai_image_prompts: list[AiImagePrompt] = Field(default_factory=list)
    compressed_context: CompressedContextPack | None = None
    auditor_panel: AuditorPanelReport | None = None
    """Cloud Hardening — UUID tenant workspace under python/out/<job_id>/."""
    job_id: str | None = None
    job_out_dir: str | None = None
    emitted_python_path: str | None = None
    notes: list[str] = Field(default_factory=list)


def empty_scene_ir(user_prompt: str = "") -> SceneIR:
    """Factory for graph entry."""
    return SceneIR(user_prompt=user_prompt)


def empty_compliance_pending() -> ComplianceReport:
    """All flags False until validators run."""
    return ComplianceReport()
