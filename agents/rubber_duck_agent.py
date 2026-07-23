"""
RubberDuckAgent — Virtual Rubber Duck for agent dialogue and design critique.

Why: A "rubber duck" that questions every agent's output, validates against
Williams animation principles, continuity rules, and quality checklist —
surfacing issues to the user in natural Persian before render.

The duck is:
  - Deterministic first (rule-based checks from craft packs)
  - Optionally LLM-enriched for deeper questioning
  - Non-blocking — it suggests, user decides
  - Mutable — can be silenced or set to "silent mode"

Architecture:
  Each agent phase produces output → Duck intercepts → Duck asks questions
  → User responds → Duck feeds back to next agent or triggers revise
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

DuckSeverity = Literal["critical", "warning", "suggestion", "praise"]
DuckPhase = Literal[
    "screenplay", "breakdown", "storyboard", "cinematography",
    "timing", "continuity", "export", "render", "general",
]


@dataclass
class DuckQuestion:
    """A single question or observation from the Rubber Duck."""

    id: str
    phase: DuckPhase
    severity: DuckSeverity
    title_fa: str  # Short Persian title
    detail_fa: str  # Full explanation in Persian
    target_shot: int | None = None  # Which shot this applies to
    target_field: str | None = None  # Which field (camera, pose, duration, etc.)
    suggested_fix: str | None = None  # Concrete suggestion
    suggested_value: Any = None  # Suggested new value
    rule_ref: str | None = None  # Reference to Williams principle / QC rule
    needs_user_decision: bool = False  # True if user must decide

    def severity_icon(self) -> str:
        icons = {
            "critical": "⚠",
            "warning": "⚡",
            "suggestion": "💡",
            "praise": "✅",
        }
        return icons.get(self.severity, "•")


@dataclass
class DuckSession:
    """Accumulated duck state across one design session."""

    questions: list[DuckQuestion] = field(default_factory=list)
    answered: set[str] = field(default_factory=set)  # IDs of resolved questions
    muted: bool = False
    strictness: str = "normal"  # "silent" | "gentle" | "normal" | "strict"
    total_critical: int = 0
    total_warnings: int = 0
    total_suggestions: int = 0


# ── Persian message templates ───────────────────────────────────────

_MSG = {
    "screenplay_scene_count": (
        "تعداد صحنه‌ها",
        "سناریو {n} صحنه دارد. هر صحنه یک ایده اصلی دارد؟ اگر صحنه‌ای خیلی شلوغ است، بهتر است شکسته شود.",
    ),
    "screenplay_abrupt_transition": (
        " transition ناگهانی",
        "بین شات {a} و {b} transition ناگهانی به نظر می‌رسد — از «{prev}» به «{curr}» بدون beat میانی. "
        "یک شات anticipation یا quiet_hold اضافه شود؟",
    ),
    "screenplay_missing_emotion": (
        "احساس مبهم",
        "حس عاطفی شات {i} («{action}») مشخص نیست. اضافه کردن توصیف احساسی به واکنش‌پذیری بیشتر تماشاگر کمک می‌کند.",
    ),
    "breakdown_shot_focus": (
        "فوکال پوینت شات",
        "شات {i} چند ایده همزمان دارد؟ هر شات باید دقیقاً یک ایده اصلی داشته باشد. "
        "الان «{action}» — آیا یک چیز مرکزی دارد؟",
    ),
    "breakdown_beat_match": (
        "تطابق story beat",
        "story_beat شات {i} («{beat}») با action («{action}») هماهنگ است؟ "
        "اگر action توصیف دیگری دارد، beat را تغییر دهیم.",
    ),
    "storyboard_pose_check": (
        "بررسی پوز",
        "پوز شات {i} = «{pose}» برای beat={beat}. طبق اصول Williams، "
        "برای این beat پوز {expected} مناسب‌تر است. تغییر دهیم؟",
    ),
    "storyboard_duration_check": (
        "بررسی duration",
        "شات {i} duration={dur}s با {n} کلمه dialogue. "
        "حداقل زمان لازم برای خواندن دیالوگ حدود {min_s}s است. "
        "duration را افزایش دهیم؟",
    ),
    "storyboard_anticipation_missing": (
        "فقدان anticipation",
        "شات {i} beat={beat} anticipation_frames={ant} دارد. "
        "برای beat «{beat}» حداقل {min_ant} فریم anticipation توصیه می‌شود.",
    ),
    "storyboard_hold_check": (
        "بررسی hold",
        "شات {i} hold_frames={hold}. اگر hold خیلی کوتاه باشد، "
        "تماشاگر فرصت درک صحنه را ندارد. حداقل ۱۲ فریم پیشنهاد می‌شود.",
    ),
    "cine_camera_beat_match": (
        "دوربین و beat",
        "شات {i}: دوربین «{cam}» برای beat={beat}. طبق craft pack، "
        "برای این beat دوربین {expected_cam} با حرکت {expected_move} مناسب‌تر است.",
    ),
    "cine_composition_check": (
        "بررسی composition",
        "شات {i}: composition={comp}. آیا این ترکیب‌بندی با فضای نگاه ({look}) "
        "و خط ۱۸۰ درجه هماهنگ است؟",
    ),
    "cine_lens_emotion": (
        "لنز و احساس",
        "شات {i}: لنز «{lens}» برای beat={beat}. "
        "لنز beauty برای لحظات احساسی، action برای درگیری، standard برای عمومی. مناسب است؟",
    ),
    "continuity_180_violation": (
        "⚠ نقض قانون ۱۸۰ درجه",
        "شات {a} (look={la}) → شات {b} (look={lb}). "
        "خط فرضی ۱۸۰ درجه شکسته شده! یا دوربین را به سمت دیگر ببرید "
        "یا یک شات میانی (cutaway) اضافه کنید.",
    ),
    "continuity_screen_direction": (
        "جهت صفحه",
        "شات {a} screen_direction={da} و شات {b} screen_direction={db}. "
        "تغییر جهت بدون justification می‌تواند مخاطب را گیج کند.",
    ),
    "continuity_eyeline": (
        "خط نگاه",
        "شات {i}: eyeline ممکن است inconsistent باشد. "
        "اگر کاراکتر به سمت {look} نگاه می‌کند، در شات بعدی هم باید consistent بماند.",
    ),
    "timing_action_bias": (
        "action bias",
        "شات {i}: action_bias={bias}. برای beat={beat}، "
        "معمولاً {expected_bias} مناسب‌تر است (slow-in برای reaction، even برای walk).",
    ),
    "timing_too_fast": (
        "سرعت زیاد",
        "شات {i} duration={dur}s ({frames}f) برای action «{action}» "
        "به نظر خیلی سریع می‌آید. Williams می‌گوید: 'Go twice as slow' — "
        "duration را دو برابر کنیم؟",
    ),
    "export_quality_check": (
        "بررسی کیفیت خروجی",
        "{n} شات برای خروجی آماده است. آیا همه شات‌ها duration>0 دارند؟ "
        "آیا screenplay نهایی با shot table همخوانی دارد؟",
    ),
    "praise_good_arc": (
        "✅ قوس احساسی خوب",
        "emotional arc از {emotions} منطقی و smooth است. "
        "پیشرفت احساسی داستان natural به نظر می‌رسد.",
    ),
    "praise_good_rhythm": (
        "✅ ریتم خوب",
        "تناوب beatها ({beats}) ریتم خوبی ایجاد کرده — "
        "variation بین سکون و حرکت balanced است.",
    ),
}


# ── Rule-based checks ────────────────────────────────────────────────


def _load_williams_data() -> dict[str, Any]:
    """Load Williams craft pack data for duck validations."""
    try:
        from tools.williams_craft import load_williams_craft_pack

        pack = load_williams_craft_pack()
        behaviors = {
            (b.get("story_beat") or ""): b
            for b in pack.shot_behaviors
        }
        antis = {a.get("id"): a for a in pack.anti_patterns}
        return {
            "fps": pack.fps,
            "behaviors": behaviors,
            "anti_patterns": antis,
            "principles": pack.principles,
        }
    except Exception:
        return {"fps": 24, "behaviors": {}, "anti_patterns": {}, "principles": []}


def _load_quality_checks() -> list[dict[str, Any]]:
    """Load quality checklist for duck validations."""
    try:
        from libraries import load_library

        data = load_library("story", "quality_checklist.json")
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


# Pose recommendations per beat
_POSE_FOR_BEAT: dict[str, str] = {
    "entrance": "walk",
    "exit": "walk",
    "reaction": "react",
    "reveal": "walk",
    "quiet_hold": "idle",
    "conflict": "react",
    "decision": "idle",
}

# Camera recommendations per beat
_CAMERA_FOR_BEAT: dict[str, str] = {
    "entrance": "static",
    "exit": "static",
    "reaction": "motivated_push",
    "reveal": "static",
    "quiet_hold": "static",
    "conflict": "motivated_push",
    "decision": "static",
}

# Lens recommendations per beat
_LENS_FOR_BEAT: dict[str, str] = {
    "entrance": "standard",
    "exit": "standard",
    "reaction": "action",
    "reveal": "beauty",
    "quiet_hold": "beauty",
    "conflict": "action",
    "decision": "standard",
}

# Minimum anticipation frames per beat
_MIN_ANTICIPATION: dict[str, int] = {
    "entrance": 4,
    "exit": 4,
    "reaction": 6,
    "reveal": 8,
    "quiet_hold": 2,
    "conflict": 8,
    "decision": 6,
}

# Action bias per beat
_BIAS_FOR_BEAT: dict[str, str] = {
    "entrance": "even",
    "exit": "even",
    "reaction": "slow_in",
    "reveal": "slow_in",
    "quiet_hold": "even",
    "conflict": "slow_out",
    "decision": "slow_in",
}


def _estimate_read_time_sec(text: str) -> float:
    """Rough estimate: ~3 words per second for Persian/English."""
    words = len(text.split())
    return max(1.0, words / 3.0)


def _shot_id_str(i: int) -> str:
    return f"شات {i}"


# ── Main Duck Agent ──────────────────────────────────────────────────


class RubberDuckAgent:
    """Virtual Rubber Duck — questions agent outputs, validates rules, suggests fixes."""

    def __init__(self, strictness: str = "normal"):
        self._williams = _load_williams_data()
        self._qc = _load_quality_checks()
        self.session = DuckSession(strictness=strictness)
        if strictness == "silent":
            self.session.muted = True

    # ── Phase interceptors ────────────────────────────────────────

    def interrogate_screenplay(
        self, screenplay: dict[str, Any], brief: str = ""
    ) -> list[DuckQuestion]:
        """Question the draft screenplay before storyboard."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        scenes = screenplay.get("scenes") or []
        n = len(scenes)

        # Check scene count
        if n == 0:
            questions.append(DuckQuestion(
                id="sp_001",
                phase="screenplay",
                severity="critical",
                title_fa="سناریو خالی است",
                detail_fa="هیچ صحنه‌ای در سناریو شناسایی نشد. لطفاً brief را با پاراگراف‌های جداگانه بازنویسی کنید.",
                needs_user_decision=True,
            ))
        elif n == 1:
            questions.append(DuckQuestion(
                id="sp_002",
                phase="screenplay",
                severity="suggestion",
                title_fa="فقط یک صحنه",
                detail_fa="سناریو فقط یک صحنه دارد. برای انیمیشن جذاب‌تر، ۳ تا ۵ صحنه با beatهای مختلف (entrance → reaction → exit) پیشنهاد می‌شود.",
                needs_user_decision=False,
            ))

        # Check for abrupt transitions between scenes
        for i in range(len(scenes) - 1):
            curr_beat = scenes[i].get("story_beat") or scenes[i].get("beat", "")
            next_beat = scenes[i + 1].get("story_beat") or scenes[i + 1].get("beat", "")
            # Abrupt: entrance→exit, conflict→quiet_hold without transition
            abrupt_pairs = [
                ("entrance", "exit"),
                ("conflict", "quiet_hold"),
                ("reaction", "exit"),
            ]
            if (curr_beat, next_beat) in abrupt_pairs:
                questions.append(DuckQuestion(
                    id=f"sp_abrupt_{i}",
                    phase="screenplay",
                    severity="warning",
                    title_fa=" transition ناگهانی",
                    detail_fa=_MSG["screenplay_abrupt_transition"][1].format(
                        a=i, b=i + 1, prev=curr_beat, curr=next_beat,
                    ),
                    target_shot=i,
                    suggested_fix="یک شات anticipation یا quiet_hold بین این دو اضافه شود.",
                    needs_user_decision=True,
                    rule_ref="QC_004 (three-phase action)",
                ))

        # Check for missing emotion description
        for i, sc in enumerate(scenes):
            action = sc.get("action") or sc.get("body", "")
            emotion_words = ["شوک", "نگران", "خوشحال", "غمگین", "عصبانی", "متعجب",
                             "آرام", "ترس", "عشق", "تنفر", "shock", "happy", "sad",
                             "angry", "surprised", "calm", "fear", "love", "worry"]
            has_emotion = any(w in str(action).lower() for w in emotion_words)
            if not has_emotion and len(str(action)) > 5:
                questions.append(DuckQuestion(
                    id=f"sp_emo_{i}",
                    phase="screenplay",
                    severity="suggestion",
                    title_fa="احساس مبهم",
                    detail_fa=_MSG["screenplay_missing_emotion"][1].format(
                        i=i, action=str(action)[:80],
                    ),
                    target_shot=i,
                    target_field="action",
                    needs_user_decision=False,
                ))

        return questions

    def interrogate_breakdown(
        self, shots: list[dict[str, Any]]
    ) -> list[DuckQuestion]:
        """Question the script breakdown / shot list."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        for i, sh in enumerate(shots):
            action = str(sh.get("action") or sh.get("idea") or "")
            beat = str(sh.get("story_beat") or sh.get("beat") or "")

            # Check single focus
            sentences = [s.strip() for s in re.split(r"[.。!?\n]", action) if s.strip()]
            if len(sentences) > 2:
                questions.append(DuckQuestion(
                    id=f"br_focus_{i}",
                    phase="breakdown",
                    severity="warning",
                    title_fa="فوکال پوینت چندگانه",
                    detail_fa=_MSG["breakdown_shot_focus"][1].format(
                        i=i, action=action[:100],
                    ),
                    target_shot=i,
                    suggested_fix="action را به یک ایده اصلی محدود کنید.",
                    rule_ref="QC_001",
                    needs_user_decision=False,
                ))

            # Check beat-action match
            if beat and action:
                expected_beat = _infer_beat_from_action(action)
                if expected_beat and expected_beat != beat:
                    questions.append(DuckQuestion(
                        id=f"br_beat_{i}",
                        phase="breakdown",
                        severity="suggestion",
                        title_fa="تطابق beat و action",
                        detail_fa=_MSG["breakdown_beat_match"][1].format(
                            i=i, beat=beat, action=action[:80],
                        ),
                        target_shot=i,
                        target_field="story_beat",
                        suggested_value=expected_beat,
                        suggested_fix=f"beat را به '{expected_beat}' تغییر دهیم؟",
                        needs_user_decision=True,
                    ))

        return questions

    def interrogate_storyboard(
        self, shots: list[dict[str, Any]]
    ) -> list[DuckQuestion]:
        """Question storyboard decisions: pose, duration, anticipation, hold."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        for i, sh in enumerate(shots):
            beat = str(sh.get("story_beat") or sh.get("beat") or "")
            pose = str(sh.get("pose") or "")
            dialogue = str(sh.get("dialogue") or "")
            dur = float(sh.get("duration_sec") or 3.0)
            ant = int(sh.get("anticipation_frames") or 0)
            hold = int(sh.get("hold_frames") or 0)
            dur_frames = int(sh.get("duration_frames") or max(12, round(dur * 24)))

            # Pose check
            expected_pose = _POSE_FOR_BEAT.get(beat)
            if expected_pose and pose and pose != expected_pose:
                questions.append(DuckQuestion(
                    id=f"sb_pose_{i}",
                    phase="storyboard",
                    severity="suggestion",
                    title_fa="پوز پیشنهادی",
                    detail_fa=_MSG["storyboard_pose_check"][1].format(
                        i=i, pose=pose, beat=beat, expected=expected_pose,
                    ),
                    target_shot=i,
                    target_field="pose",
                    suggested_value=expected_pose,
                    needs_user_decision=True,
                    rule_ref="Williams: pose library",
                ))

            # Duration vs dialogue
            if dialogue.strip():
                min_sec = _estimate_read_time_sec(dialogue)
                if dur < min_sec:
                    questions.append(DuckQuestion(
                        id=f"sb_dur_{i}",
                        phase="storyboard",
                        severity="warning",
                        title_fa="duration کم برای دیالوگ",
                        detail_fa=_MSG["storyboard_duration_check"][1].format(
                            i=i, dur=dur, n=len(dialogue.split()), min_s=round(min_sec, 1),
                        ),
                        target_shot=i,
                        target_field="duration_sec",
                        suggested_value=round(min_sec + 0.5, 1),
                        needs_user_decision=True,
                    ))

            # Anticipation check
            min_ant = _MIN_ANTICIPATION.get(beat, 4)
            if ant < min_ant:
                questions.append(DuckQuestion(
                    id=f"sb_ant_{i}",
                    phase="storyboard",
                    severity="suggestion",
                    title_fa="anticipation کم",
                    detail_fa=_MSG["storyboard_anticipation_missing"][1].format(
                        i=i, beat=beat, ant=ant, min_ant=min_ant,
                    ),
                    target_shot=i,
                    target_field="anticipation_frames",
                    suggested_value=min_ant,
                    needs_user_decision=True,
                    rule_ref="Williams: anticipation principle",
                ))

            # Hold check
            if hold < 8 and beat not in ("entrance", "exit"):
                questions.append(DuckQuestion(
                    id=f"sb_hold_{i}",
                    phase="storyboard",
                    severity="suggestion",
                    title_fa="hold کوتاه",
                    detail_fa=_MSG["storyboard_hold_check"][1].format(i=i, hold=hold),
                    target_shot=i,
                    target_field="hold_frames",
                    suggested_value=12,
                    needs_user_decision=False,
                ))

            # Too fast check (Williams anti-pattern)
            if dur_frames < 24 and len(str(sh.get("action", ""))) > 30:
                questions.append(DuckQuestion(
                    id=f"sb_fast_{i}",
                    phase="storyboard",
                    severity="warning",
                    title_fa="سرعت زیاد",
                    detail_fa=_MSG["timing_too_fast"][1].format(
                        i=i, dur=dur, frames=dur_frames,
                        action=str(sh.get("action", ""))[:60],
                    ),
                    target_shot=i,
                    target_field="duration_sec",
                    suggested_value=round(dur * 2, 1),
                    needs_user_decision=True,
                    rule_ref="Williams: major_beginner_mistake_too_fast",
                ))

        return questions

    def interrogate_cinematography(
        self, shots: list[dict[str, Any]], cine_frames: list[dict[str, Any]] | None = None
    ) -> list[DuckQuestion]:
        """Question cinematography decisions."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        cine_by_id = {}
        if cine_frames:
            cine_by_id = {
                f.get("shot_id"): f for f in cine_frames
            }

        for i, sh in enumerate(shots):
            sid = sh.get("shot_id", i)
            crow = cine_by_id.get(sid) or {}
            beat = str(sh.get("story_beat") or sh.get("beat") or "")
            cam = str(crow.get("camera") or sh.get("camera") or "static")
            lens = str(crow.get("lens") or sh.get("lens") or "standard")
            comp = str(crow.get("composition") or sh.get("composition_shape") or "C")
            look = str(crow.get("look_space_direction") or sh.get("look_space") or "")

            # Camera-beat match
            expected_cam = _CAMERA_FOR_BEAT.get(beat, "static")
            if cam != expected_cam and self.session.strictness in ("normal", "strict"):
                questions.append(DuckQuestion(
                    id=f"cine_cam_{i}",
                    phase="cinematography",
                    severity="suggestion",
                    title_fa="دوربین و beat",
                    detail_fa=_MSG["cine_camera_beat_match"][1].format(
                        i=i, cam=cam, beat=beat, expected_cam=expected_cam,
                        expected_move=expected_cam,
                    ),
                    target_shot=i,
                    target_field="camera",
                    suggested_value=expected_cam,
                    needs_user_decision=True,
                ))

            # Lens-emotion check
            expected_lens = _LENS_FOR_BEAT.get(beat, "standard")
            if lens != expected_lens and self.session.strictness == "strict":
                questions.append(DuckQuestion(
                    id=f"cine_lens_{i}",
                    phase="cinematography",
                    severity="suggestion",
                    title_fa="لنز و احساس",
                    detail_fa=_MSG["cine_lens_emotion"][1].format(
                        i=i, lens=lens, beat=beat,
                    ),
                    target_shot=i,
                    target_field="lens",
                    suggested_value=expected_lens,
                    needs_user_decision=False,
                ))

        return questions

    def interrogate_continuity(
        self, shots: list[dict[str, Any]], continuity: dict[str, Any] | None = None
    ) -> list[DuckQuestion]:
        """Validate continuity: 180° rule, screen direction, eyeline."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        cont = continuity or {}

        # Check 180° violations
        violations = cont.get("violations") or []
        for v in violations:
            questions.append(DuckQuestion(
                id=f"cont_180_{v.get('shot_id', '?')}",
                phase="continuity",
                severity="critical",
                title_fa="⚠ نقض قانون ۱۸۰ درجه",
                detail_fa=str(v.get("detail") or v),
                target_shot=v.get("shot_id"),
                needs_user_decision=True,
                rule_ref="QC_005",
            ))

        # Check line side consistency
        line_side = cont.get("180_line_side") or cont.get("line_side", "")
        checks = cont.get("checks") or []
        prev_direction = None
        for i, ch in enumerate(checks):
            direction = ch.get("screen_direction", "")
            if prev_direction and direction != prev_direction:
                questions.append(DuckQuestion(
                    id=f"cont_dir_{i}",
                    phase="continuity",
                    severity="warning",
                    title_fa="تغییر جهت صفحه",
                    detail_fa=_MSG["continuity_screen_direction"][1].format(
                        a=i - 1, da=prev_direction, b=i, db=direction,
                    ),
                    target_shot=i,
                    needs_user_decision=False,
                    rule_ref="QC_005",
                ))
            prev_direction = direction

        # Eyeline consistency
        for i, ch in enumerate(checks):
            eyeline = ch.get("eyeline", "")
            if eyeline == "inconsistent":
                look_dir = ch.get("look_space_direction", "?")
                questions.append(DuckQuestion(
                    id=f"cont_eye_{i}",
                    phase="continuity",
                    severity="warning",
                    title_fa="خط نگاه inconsistent",
                    detail_fa=_MSG["continuity_eyeline"][1].format(
                        i=i, look=look_dir,
                    ),
                    target_shot=i,
                    needs_user_decision=False,
                    rule_ref="QC_005",
                ))

        return questions

    def interrogate_timing(
        self, shots: list[dict[str, Any]]
    ) -> list[DuckQuestion]:
        """Validate animation timing."""
        if self.session.muted or self.session.strictness == "silent":
            return []

        questions: list[DuckQuestion] = []
        for i, sh in enumerate(shots):
            beat = str(sh.get("story_beat") or sh.get("beat") or "")
            bias = str(sh.get("action_bias") or "even")
            expected_bias = _BIAS_FOR_BEAT.get(beat, "even")

            if bias != expected_bias and self.session.strictness in ("normal", "strict"):
                questions.append(DuckQuestion(
                    id=f"tim_bias_{i}",
                    phase="timing",
                    severity="suggestion",
                    title_fa="action bias",
                    detail_fa=_MSG["timing_action_bias"][1].format(
                        i=i, bias=bias, beat=beat, expected_bias=expected_bias,
                    ),
                    target_shot=i,
                    target_field="action_bias",
                    suggested_value=expected_bias,
                    needs_user_decision=False,
                ))

        return questions

    def interrogate_export(
        self, shots: list[dict[str, Any]], bundle: dict[str, Any] | None = None
    ) -> list[DuckQuestion]:
        """Final quality check before render."""
        if self.session.muted:
            return []

        questions: list[DuckQuestion] = []
        n = len(shots)

        # Check all shots have duration
        bad_shots = [
            i for i, sh in enumerate(shots)
            if float(sh.get("duration_sec") or 0) <= 0
        ]
        if bad_shots:
            questions.append(DuckQuestion(
                id="exp_nodur",
                phase="export",
                severity="critical",
                title_fa="شات بدون duration",
                detail_fa=f"شات‌های {bad_shots} duration=0 دارند. رندر با خطا مواجه می‌شود.",
                needs_user_decision=True,
            ))

        # Overall praise when things look good
        if n >= 3 and not bad_shots:
            beats = [sh.get("story_beat", "") for sh in shots]
            unique_beats = len(set(b for b in beats if b))
            if unique_beats >= 2:
                questions.append(DuckQuestion(
                    id="exp_praise",
                    phase="export",
                    severity="praise",
                    title_fa=_MSG["praise_good_rhythm"][0],
                    detail_fa=_MSG["praise_good_rhythm"][1].format(
                        beats=" → ".join(beats),
                    ),
                    needs_user_decision=False,
                ))

        return questions

    # ── Aggregate ─────────────────────────────────────────────────

    def interrogate_all(
        self,
        *,
        screenplay: dict[str, Any] | None = None,
        shots: list[dict[str, Any]] | None = None,
        cine_frames: list[dict[str, Any]] | None = None,
        continuity: dict[str, Any] | None = None,
        bundle: dict[str, Any] | None = None,
        phase: DuckPhase | None = None,
        brief: str = "",
    ) -> list[DuckQuestion]:
        """Run all relevant interrogations based on provided data."""
        all_q: list[DuckQuestion] = []

        shots = shots or []

        if screenplay and (not phase or phase == "screenplay"):
            all_q.extend(self.interrogate_screenplay(screenplay, brief))

        if shots:
            if not phase or phase == "breakdown":
                all_q.extend(self.interrogate_breakdown(shots))
            if not phase or phase == "storyboard":
                all_q.extend(self.interrogate_storyboard(shots))
            if not phase or phase == "cinematography":
                all_q.extend(self.interrogate_cinematography(shots, cine_frames))
            if not phase or phase == "timing":
                all_q.extend(self.interrogate_timing(shots))
            if not phase or phase == "continuity":
                all_q.extend(self.interrogate_continuity(shots, continuity))
            if not phase or phase == "export":
                all_q.extend(self.interrogate_export(shots, bundle))

        # Track in session
        self.session.questions.extend(all_q)
        self.session.total_critical += sum(1 for q in all_q if q.severity == "critical")
        self.session.total_warnings += sum(1 for q in all_q if q.severity == "warning")
        self.session.total_suggestions += sum(1 for q in all_q if q.severity == "suggestion")

        return all_q

    def mark_answered(self, question_id: str) -> None:
        """Mark a duck question as resolved."""
        self.session.answered.add(question_id)

    def unanswered(self) -> list[DuckQuestion]:
        """Questions that still need user attention."""
        return [
            q for q in self.session.questions
            if q.id not in self.session.answered
        ]

    def critical_unanswered(self) -> list[DuckQuestion]:
        """Unanswered critical questions."""
        return [q for q in self.unanswered() if q.severity == "critical"]

    def summary_fa(self) -> str:
        """One-line Persian summary of duck findings."""
        parts = []
        if self.session.total_critical:
            parts.append(f"⚠ {self.session.total_critical} بحرانی")
        if self.session.total_warnings:
            parts.append(f"⚡ {self.session.total_warnings} اخطار")
        if self.session.total_suggestions:
            parts.append(f"💡 {self.session.total_suggestions} پیشنهاد")
        if not parts:
            return "✅ همه چیز خوب به نظر می‌رسد!"
        return " | ".join(parts)

    def set_strictness(self, level: str) -> None:
        """Change duck strictness: silent, gentle, normal, strict."""
        self.session.strictness = level
        self.session.muted = (level == "silent")


# ── Helpers ─────────────────────────────────────────────────────────


def _infer_beat_from_action(action: str) -> str | None:
    """Simple keyword-based beat inference from action text."""
    action_lower = action.lower()
    keywords = [
        ("entrance", ["وارد", "enter", "arrive", "comes in", "opens door"]),
        ("exit", ["خارج", "exit", "leave", "depart", "goes out", "می‌رود"]),
        ("reaction", ["شوک", "shock", "react", "surprised", "gasp", "متعجب", "واکنش"]),
        ("reveal", ["کشف", "reveal", "discover", "finds", "sees", "پیدا", "نمایان"]),
        ("conflict", ["درگیری", "fight", "conflict", "clash", "حمله", "attack"]),
        ("decision", ["تصمیم", "decide", "chooses", "resolve", "انتخاب"]),
        ("quiet_hold", ["آرام", "quiet", "still", "pause", "breathe", "سکوت", "مکث"]),
    ]
    for beat, kws in keywords:
        if any(kw in action_lower for kw in kws):
            return beat
    return None


def run_rubber_duck(
    *,
    screenplay: dict[str, Any] | None = None,
    shots: list[dict[str, Any]] | None = None,
    cine_frames: list[dict[str, Any]] | None = None,
    continuity: dict[str, Any] | None = None,
    bundle: dict[str, Any] | None = None,
    phase: DuckPhase | None = None,
    brief: str = "",
    strictness: str = "normal",
) -> tuple[RubberDuckAgent, list[DuckQuestion]]:
    """Convenience: create duck, interrogate, return both."""
    duck = RubberDuckAgent(strictness=strictness)
    questions = duck.interrogate_all(
        screenplay=screenplay,
        shots=shots,
        cine_frames=cine_frames,
        continuity=continuity,
        bundle=bundle,
        phase=phase,
        brief=brief,
    )
    return duck, questions