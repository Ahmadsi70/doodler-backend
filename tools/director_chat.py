"""
Director Chat — message protocol, session manager, and command parser.

Why: The chat-based Director interface needs a typed message bus, a session
that accumulates agent outputs, and a command parser that translates user
natural-language prompts into structured edit actions.

Protocol:
  ChatMessage  — one message in the conversation
  ChatSession  — full conversation state + agent pipeline bridge
  CommandParser — user text → structured Command
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass as _dataclass, field as _field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal


# ── Message types ────────────────────────────────────────────────────


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    RUBBER_DUCK = "rubber_duck"


class ContentType(Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    TABLE = "table"
    CODE = "code"
    SHOT_CARD = "shot_card"
    JSON = "json"
    STATUS = "status"


@_dataclass
class ChatMessage:
    """One message in the Director Chat conversation."""

    role: MessageRole
    content: str
    agent_name: str = ""  # e.g. "DraftScreenplay", "RubberDuck"
    content_type: ContentType = ContentType.TEXT
    data: dict[str, Any] | None = None  # Structured payload (shot data, etc.)
    phase: str = ""  # screenplay, breakdown, storyboard, etc.
    needs_reply: bool = False
    suggestions: list[str] = _field(default_factory=list)  # Quick-reply options
    timestamp: str = ""


# ── Command types ─────────────────────────────────────────────────────


class CommandKind(Enum):
    BRIEF = "brief"               # Submit story brief
    APPROVE = "approve"           # Approve current artifact
    REJECT = "reject"             # Reject / request revision
    EDIT_SHOT = "edit_shot"       # Edit a specific shot field
    ADD_SHOT = "add_shot"         # Insert a new shot
    REMOVE_SHOT = "remove_shot"   # Delete a shot
    REVISE = "revise"             # Free-form revise prompt
    ASK_DUCK = "ask_duck"         # Ask the duck a question
    MUTE_DUCK = "mute_duck"       # Silence the duck
    UNMUTE_DUCK = "unmute_duck"   # Re-enable the duck
    SET_QUALITY = "set_quality"   # Change quality (light/pro)
    RENDER = "render"             # Trigger render
    EXPORT = "export"             # Export bundle only
    RESET = "reset"               # Start over
    SKIP = "skip"                 # Skip current phase / continue
    UNKNOWN = "unknown"           # Unrecognized command


@_dataclass
class Command:
    """Parsed user command from chat input."""

    kind: CommandKind
    raw_text: str = ""
    shot_index: int | None = None
    field: str | None = None
    value: Any = None
    prompt: str = ""  # For revise / ask_duck
    metadata: dict[str, Any] = _field(default_factory=dict)


# ── Command Parser ────────────────────────────────────────────────────


class CommandParser:
    """
    Parse Persian/English natural language into structured Command objects.

    Supports:
      - Explicit commands: "شات ۲ دوربین static"
      - Brief submission: long text with paragraphs
      - Approve: "تأیید", "ok", "برو بعدی"
      - Duck control: "duck quiet", "duck talk", "اردک ساکت"
    """

    # Persian / English keyword mappings
    APPROVE_WORDS = {
        "تأیید", "تایید", "ok", "yes", "آره", "بله", "برو", "قبول",
        "ادامه", "برو بعدی", "next", "confirm", "approve", "good",
    }
    REJECT_WORDS = {
        "نه", "no", "رد", "برگرد", "لغو", "cancel", "reject", "back",
    }
    SKIP_WORDS = {
        "بگذر", "skip", "عبور", "بعدی", "continue",
    }
    RENDER_WORDS = {
        "رندر", "render", "خروجی بگیر", "mp4", "فیلم بساز",
    }
    EXPORT_WORDS = {
        "export", "صدور", "خروجی", "کد بده", "code",
    }

    # Field name mappings (Persian → English field key)
    FIELD_MAP: dict[str, str] = {
        # Persian
        "دوربین": "camera", "کمرا": "camera",
        "پوز": "pose", "حالت": "pose",
        "لنز": "lens",
        "مدت": "duration_sec", "زمان": "duration_sec", "duration": "duration_sec",
        "ثانیه": "duration_sec",
        "دیالوگ": "dialogue", "گفتگو": "dialogue",
        "beat": "story_beat", "ضرب": "story_beat",
        "اکشن": "action", "عمل": "action",
        "عنوان": "title", "اسم": "title",
        "composition": "composition", "comp": "composition", "ترکیب": "composition",
        "نور": "lighting", "نورپردازی": "lighting",
        "اندازه": "shot_size", "سایز": "shot_size",
        "anticipation": "anticipation_frames", "پیش‌بینی": "anticipation_frames",
        "hold": "hold_frames", "نگه‌داری": "hold_frames",
        "expression": "expression", "حالت چهره": "expression",
        "look": "look_space", "نگاه": "look_space",
        # English
        "camera": "camera", "pose": "pose", "lens": "lens",
        "duration_sec": "duration_sec", "dialogue": "dialogue",
        "story_beat": "story_beat", "beat": "story_beat",
        "action": "action", "title": "title",
        "composition": "composition", "comp": "composition",
        "lighting": "lighting",
        "shot_size": "shot_size",
        "anticipation_frames": "anticipation_frames",
        "hold_frames": "hold_frames",
        "expression": "expression",
        "look_space": "look_space",
    }

    # Camera values
    CAMERA_VALUES = {
        "static", "ثابت",
        "motivated_push", "push", "هل", "حرکت به جلو",
        "pan", "پن",
        "tilt", "تیلت",
        "track", "tracking", "دنبال",
    }

    # Pose values
    POSE_VALUES = {
        "idle", "ایستاده", "ساکن",
        "walk", "راه", "قدم",
        "react", "واکنش", "عکس‌العمل",
        "run", "دویدن",
        "jump", "پرش",
    }

    # Composition values
    COMP_VALUES = {
        "L", "چپ", "left",
        "C", "وسط", "center", "مرکز",
        "R", "راست", "right",
    }

    # Lens values
    LENS_VALUES = {
        "standard", "استاندارد",
        "beauty", "زیبایی",
        "action", "اکشن",
        "wide", "واید", "باز",
    }

    # Beat values
    BEAT_VALUES = {
        "entrance", "ورود",
        "exit", "خروج",
        "reaction", "واکنش",
        "reveal", "افشا", "کشف",
        "conflict", "درگیری",
        "decision", "تصمیم",
        "quiet_hold", "مکث", "سکوت",
    }

    # Duck control words
    DUCK_MUTE_WORDS = {
        "اردک ساکت", "duck mute", "duck quiet", "duck silent",
        "ساکت شو", "خفه شو اردک", "بسه اردک", "خاموش اردک",
    }
    DUCK_UNMUTE_WORDS = {
        "اردک صحبت کن", "duck speak", "duck talk", "duck unmute",
        "حرف بزن", "صحبت کن", "برگرد اردک",
    }
    DUCK_ASK_WORDS = {
        "اردک", "duck", "🦆",
    }

    QUALITY_VALUES = {"light", "pro", "سبک", "حرفه‌ای", "ساده"}

    @classmethod
    def parse(cls, text: str) -> Command:
        """Parse user text into a structured Command."""
        text = text.strip()
        if not text:
            return Command(kind=CommandKind.UNKNOWN, raw_text=text)

        text_lower = text.lower().replace("،", " ").replace("؛", " ")

        # ── Brief detection (multi-line or narrative style) ──
        # Multi-line with at least 2 non-empty paragraphs
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if len(paragraphs) >= 2:
            return Command(kind=CommandKind.BRIEF, raw_text=text, prompt=text)

        # Single long paragraph that looks like narrative
        if len(text) > 80 and not any(
            kw in text_lower
            for kw in (
                "شات", "shot", "دوربین", "camera", "پوز", "pose",
                "اردک", "duck", "تأیید", "ok", "رندر", "render",
            )
        ):
            return Command(kind=CommandKind.BRIEF, raw_text=text, prompt=text)

        # ── Single-word commands ──
        first_word = text_lower.split()[0] if text_lower.split() else ""

        # Approve
        if any(w in text_lower for w in cls.APPROVE_WORDS):
            return Command(kind=CommandKind.APPROVE, raw_text=text)

        # Reject
        if any(w == text_lower or text_lower.startswith(w + " ") or text_lower == w
               for w in cls.REJECT_WORDS):
            return Command(kind=CommandKind.REJECT, raw_text=text)

        # Skip
        if any(w in text_lower for w in cls.SKIP_WORDS):
            return Command(kind=CommandKind.SKIP, raw_text=text)

        # Render
        if any(w in text_lower for w in cls.RENDER_WORDS):
            return Command(kind=CommandKind.RENDER, raw_text=text)

        # Export code
        if any(w in text_lower for w in cls.EXPORT_WORDS):
            return Command(kind=CommandKind.EXPORT, raw_text=text)

        # Duck mute
        if any(w in text_lower for w in cls.DUCK_MUTE_WORDS):
            return Command(kind=CommandKind.MUTE_DUCK, raw_text=text)

        # Duck unmute
        if any(w in text_lower for w in cls.DUCK_UNMUTE_WORDS):
            return Command(kind=CommandKind.UNMUTE_DUCK, raw_text=text)

        # Ask duck
        if any(w in text_lower for w in cls.DUCK_ASK_WORDS) and len(text) > 10:
            return Command(kind=CommandKind.ASK_DUCK, raw_text=text, prompt=text)

        # Quality
        if first_word == "quality" or first_word == "کیفیت":
            for q in cls.QUALITY_VALUES:
                if q in text_lower:
                    return Command(kind=CommandKind.SET_QUALITY, raw_text=text, value=q)

        # Reset
        if text_lower in ("reset", "شروع دوباره", "جدید", "از اول"):
            return Command(kind=CommandKind.RESET, raw_text=text)

        # ── Shot edit: "shot X field value" ──
        cmd = cls._parse_shot_edit(text, text_lower)
        if cmd.kind != CommandKind.UNKNOWN:
            return cmd

        # ── Fallback: treat as revise prompt ──
        return Command(kind=CommandKind.REVISE, raw_text=text, prompt=text)

    @classmethod
    def _parse_shot_edit(cls, text: str, text_lower: str) -> Command:
        """Try to parse 'shot N field value' pattern."""
        # Pattern: "shot N" or "شات N"
        shot_match = re.match(
            r'(?:shot|شات)\s*(\d+)',
            text_lower,
        )
        if not shot_match:
            return Command(kind=CommandKind.UNKNOWN, raw_text=text)

        shot_idx = int(shot_match.group(1))
        remainder = text[shot_match.end():].strip()
        if not remainder:
            return Command(kind=CommandKind.UNKNOWN, raw_text=text)

        # Try: "field value"
        for fname, fkey in cls.FIELD_MAP.items():
            if remainder.lower().startswith(fname.lower()):
                val = remainder[len(fname):].strip()
                if not val:
                    return Command(
                        kind=CommandKind.EDIT_SHOT,
                        raw_text=text,
                        shot_index=shot_idx,
                        field=fkey,
                    )
                # Normalize value
                normalized = cls._normalize_value(fkey, val)
                return Command(
                    kind=CommandKind.EDIT_SHOT,
                    raw_text=text,
                    shot_index=shot_idx,
                    field=fkey,
                    value=normalized,
                )

        # Try: just a value (field inferred from context — caller sets)
        # For now, treat as revise
        return Command(kind=CommandKind.REVISE, raw_text=text, prompt=text)

    @classmethod
    def _normalize_value(cls, field: str, raw: str) -> Any:
        """Normalize a user-provided value to the correct type/format."""
        raw = raw.strip().strip('"').strip("'").strip("«").strip("»")

        # Numeric fields
        if field in ("duration_sec", "anticipation_frames", "hold_frames"):
            try:
                nums = re.findall(r'[\d.]+', raw)
                if nums:
                    return float(nums[0]) if "." in nums[0] else int(nums[0])
            except (ValueError, IndexError):
                pass
            return raw

        # Camera
        if field == "camera":
            val_lower = raw.lower()
            if val_lower in ("static", "ثابت"):
                return "static"
            if val_lower in ("motivated_push", "push", "هل", "حرکت به جلو"):
                return "motivated_push"
            if val_lower in ("pan", "پن"):
                return "pan"
            return raw

        # Pose
        if field == "pose":
            val_lower = raw.lower()
            if val_lower in ("idle", "ایستاده", "ساکن"):
                return "idle"
            if val_lower in ("walk", "راه", "قدم"):
                return "walk"
            if val_lower in ("react", "واکنش", "عکس‌العمل"):
                return "react"
            if val_lower in ("run", "دویدن"):
                return "run"
            return raw

        # Composition
        if field == "composition":
            val_upper = raw.upper()
            if val_upper in ("L", "LEFT", "چپ"):
                return "L"
            if val_upper in ("C", "CENTER", "وسط", "مرکز"):
                return "C"
            if val_upper in ("R", "RIGHT", "راست"):
                return "R"
            return val_upper[:1] if val_upper else "C"

        # Beat
        if field == "story_beat":
            val_lower = raw.lower()
            for beat in cls.BEAT_VALUES:
                if val_lower == beat.lower():
                    return beat
            return raw

        # Lens
        if field == "lens":
            val_lower = raw.lower()
            if val_lower in ("standard", "استاندارد"):
                return "standard"
            if val_lower in ("beauty", "زیبایی"):
                return "beauty"
            if val_lower in ("action", "اکشن"):
                return "action"
            if val_lower in ("wide", "واید", "باز"):
                return "wide"
            return raw

        return raw


# ── Chat Session ───────────────────────────────────────────────────────


@_dataclass
class ChatSession:
    """Manages the full Director Chat conversation and bridges to agents."""

    messages: list[ChatMessage] = _field(default_factory=list)
    brief: str = ""
    job_dir: str = ""
    current_phase: str = "idle"
    board: Any = None  # DirectorBoard (lazy import)
    duck: Any = None  # RubberDuckAgent (lazy import)
    duck_enabled: bool = True
    quality: str = "light"
    approved: bool = False
    exported: bool = False
    rendered: bool = False
    error: str | None = None

    # ── Message helpers ──────────────────────────────────────────

    def add_message(
        self,
        role: MessageRole,
        content: str,
        *,
        agent_name: str = "",
        content_type: ContentType = ContentType.TEXT,
        data: dict[str, Any] | None = None,
        phase: str = "",
        needs_reply: bool = False,
        suggestions: list[str] | None = None,
    ) -> ChatMessage:
        """Add a message to the conversation and return it."""
        msg = ChatMessage(
            role=role,
            content=content,
            agent_name=agent_name,
            content_type=content_type,
            data=data,
            phase=phase or self.current_phase,
            needs_reply=needs_reply,
            suggestions=suggestions or [],
        )
        self.messages.append(msg)
        return msg

    def system(self, text: str, **kwargs) -> ChatMessage:
        return self.add_message(MessageRole.SYSTEM, text, **kwargs)

    def user_msg(self, text: str, **kwargs) -> ChatMessage:
        return self.add_message(MessageRole.USER, text, **kwargs)

    def agent(self, text: str, agent_name: str, **kwargs) -> ChatMessage:
        return self.add_message(
            MessageRole.AGENT, text, agent_name=agent_name, **kwargs,
        )

    def duck_msg(self, text: str, **kwargs) -> ChatMessage:
        return self.add_message(
            MessageRole.RUBBER_DUCK, text, agent_name="🦆 RubberDuck", **kwargs,
        )

    def status(self, text: str, **kwargs) -> ChatMessage:
        return self.add_message(
            MessageRole.SYSTEM, text,
            content_type=ContentType.STATUS, agent_name="⚙️",
            **kwargs,
        )

    # ── Duck integration ─────────────────────────────────────────

    def ask_duck(
        self,
        *,
        screenplay: dict[str, Any] | None = None,
        shots: list[dict[str, Any]] | None = None,
        cine_frames: list[dict[str, Any]] | None = None,
        continuity: dict[str, Any] | None = None,
        bundle: dict[str, Any] | None = None,
        phase: str = "",
    ) -> list[Any]:
        """Run RubberDuck interrogate and add findings as chat messages."""
        if not self.duck_enabled:
            return []

        if self.duck is None:
            from agents.rubber_duck_agent import RubberDuckAgent
            self.duck = RubberDuckAgent()

        questions = self.duck.interrogate_all(
            screenplay=screenplay,
            shots=shots,
            cine_frames=cine_frames,
            continuity=continuity,
            bundle=bundle,
            phase=phase if phase else None,  # type: ignore[arg-type]
            brief=self.brief,
        )

        # Add duck summary
        summary = self.duck.summary_fa()
        if questions:
            self.duck_msg(f"**{summary}**\n\n" + "\n\n".join(
                f"### {q.severity_icon()} {q.title_fa}\n{q.detail_fa}"
                + (f"\n\n> 💡 پیشنهاد: {q.suggested_fix}" if q.suggested_fix else "")
                + (f"\n\n*{q.rule_ref}*" if q.rule_ref else "")
                for q in questions[:6]  # Limit to top 6
            ), phase=phase or self.current_phase)

        criticals = self.duck.critical_unanswered()
        if criticals:
            self.duck_msg(
                f"⚠ **{len(criticals)} مشکل بحرانی نیاز به توجه شما دارد.**",
                needs_reply=True,
                suggestions=["رفع کن", "بعداً", "نادیده بگیر"],
                phase=phase or self.current_phase,
            )

        return questions

    # ── Command handling ──────────────────────────────────────────

    def handle_command(self, cmd: Command) -> list[ChatMessage]:
        """Execute a parsed command, return new messages generated."""
        new_msgs: list[ChatMessage] = []

        if cmd.kind == CommandKind.BRIEF:
            self.brief = cmd.raw_text
            self.current_phase = "brief_received"
            new_msgs.append(self.system(
                f"سناریو دریافت شد — {len(cmd.raw_text.split(chr(10)))} پاراگراف",
                phase="brief",
            ))

        elif cmd.kind == CommandKind.APPROVE:
            self.approved = True
            new_msgs.append(self.system("✅ تأیید شد.", phase=self.current_phase))

        elif cmd.kind == CommandKind.REJECT:
            self.approved = False
            new_msgs.append(self.system(
                "❌ رد شد. لطفاً بگویید چه چیزی را تغییر دهیم.",
                phase=self.current_phase,
                needs_reply=True,
            ))

        elif cmd.kind == CommandKind.SKIP:
            new_msgs.append(self.system("⏭ رد شد — ادامه...", phase=self.current_phase))

        elif cmd.kind == CommandKind.EDIT_SHOT:
            if cmd.shot_index is not None and cmd.field:
                new_msgs.append(self.system(
                    f"✏️ شات {cmd.shot_index}: {cmd.field} ← {cmd.value}",
                    phase=self.current_phase,
                ))
            else:
                new_msgs.append(self.system(
                    "⚠ دستور ویرایش نامفهوم. فرمت: `شات ۲ دوربین static`",
                    phase=self.current_phase,
                ))

        elif cmd.kind == CommandKind.REVISE:
            new_msgs.append(self.system(
                f"📝 پرامپت ویرایش دریافت شد: «{cmd.prompt[:80]}...»",
                phase=self.current_phase,
            ))

        elif cmd.kind == CommandKind.ASK_DUCK:
            new_msgs.append(self.duck_msg(
                f"سوال خوبی پرسیدی! بذار بررسی کنم: «{cmd.prompt}»",
                phase=self.current_phase,
            ))

        elif cmd.kind == CommandKind.MUTE_DUCK:
            self.duck_enabled = False
            if self.duck:
                self.duck.set_strictness("silent")
            new_msgs.append(self.system("🦆🔇 اردک ساکت شد.", phase=self.current_phase))

        elif cmd.kind == CommandKind.UNMUTE_DUCK:
            self.duck_enabled = True
            if self.duck:
                self.duck.set_strictness("normal")
            new_msgs.append(self.system("🦆🔊 اردک برگشت!", phase=self.current_phase))

        elif cmd.kind == CommandKind.SET_QUALITY:
            self.quality = str(cmd.value or "light")
            new_msgs.append(self.system(
                f"کیفیت روی '{self.quality}' تنظیم شد.",
                phase=self.current_phase,
            ))

        elif cmd.kind == CommandKind.RENDER:
            new_msgs.append(self.system(
                "🎬 درخواست رندر دریافت شد...",
                phase="render",
            ))

        elif cmd.kind == CommandKind.EXPORT:
            new_msgs.append(self.system(
                "📦 درخواست صدور کد دریافت شد...",
                phase="export",
            ))

        elif cmd.kind == CommandKind.RESET:
            self.messages.clear()
            self.brief = ""
            self.current_phase = "idle"
            self.approved = False
            self.exported = False
            self.rendered = False
            new_msgs.append(self.system("🔄 همه چیز ریست شد. پروژه جدید شروع کنید."))

        return new_msgs

    # ── Persistence ──────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief,
            "current_phase": self.current_phase,
            "quality": self.quality,
            "approved": self.approved,
            "exported": self.exported,
            "rendered": self.rendered,
            "duck_enabled": self.duck_enabled,
            "messages": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "agent_name": m.agent_name,
                    "content_type": m.content_type.value,
                    "phase": m.phase,
                    "needs_reply": m.needs_reply,
                    "suggestions": m.suggestions,
                }
                for m in self.messages[-50:]  # Keep last 50
            ],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "ChatSession":
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        session = cls(
            brief=data.get("brief", ""),
            current_phase=data.get("current_phase", "idle"),
            quality=data.get("quality", "light"),
            approved=data.get("approved", False),
            exported=data.get("exported", False),
            rendered=data.get("rendered", False),
            duck_enabled=data.get("duck_enabled", True),
        )
        for m in data.get("messages") or []:
            session.messages.append(ChatMessage(
                role=MessageRole(m.get("role", "system")),
                content=m.get("content", ""),
                agent_name=m.get("agent_name", ""),
                content_type=ContentType(m.get("content_type", "text")),
                phase=m.get("phase", ""),
                needs_reply=m.get("needs_reply", False),
                suggestions=m.get("suggestions", []),
            ))
        return session


# ── Convenience ────────────────────────────────────────────────────────


def new_chat_session() -> ChatSession:
    """Create a fresh chat session with welcome message."""
    session = ChatSession()
    session.system(
        "🎬 **به Director Chat خوش آمدید!**\n\n"
        "من ایجنت‌های طراحی انیمیشن را مدیریت می‌کنم. کافیست داستان خود را به من بگویید.\n\n"
        "📝 **برای شروع**، brief خود را وارد کنید (هر پاراگراف = یک شات).\n\n"
        "نمونه:\n"
        "```\n"
        "قهرمان وارد اتاق تاریک می‌شود.\n\n"
        "نامه روی میز را پیدا می‌کند و شوکه می‌شود.\n\n"
        "آرام از در خارج می‌شود در حالی که نگران است.\n"
        "```\n\n"
        "🦆 **RubberDuck** همراه شماست و سوالات هوشمندانه‌ای می‌پرسد تا خروجی بهتر شود.\n"
        "برای ساکت کردن اردک: `اردک ساکت`",
        phase="welcome",
    )
    return session