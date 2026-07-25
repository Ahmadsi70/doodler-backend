from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .message_types import (
    Attachment,
    Message,
    MessageRole,
    MessageStatus,
    make_message_id,
)


@dataclass
class ChatSession:
    id: str = ""
    brief: str = ""
    current_phase: str = "idle"
    quality: str = "light"
    approved: bool = False
    exported: bool = False
    rendered: bool = False
    agent_states: dict[str, MessageStatus] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        *,
        agent_name: str = "",
        status: MessageStatus = MessageStatus.IDLE,
        attachments: list[Attachment] | None = None,
        needs_reply: bool = False,
        suggestions: list[str] | None = None,
        phase: str = "",
        error: str | None = None,
    ) -> Message:
        msg = Message(
            id=make_message_id(),
            role=role,
            content=content,
            agent_name=agent_name,
            status=status,
            attachments=attachments or [],
            needs_reply=needs_reply,
            suggestions=suggestions or [],
            phase=phase or self.current_phase,
            error=error,
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_user_message(self, content: str) -> Message:
        return self.add_message(MessageRole.USER, content)

    def add_system_message(self, content: str, **kwargs) -> Message:
        return self.add_message(MessageRole.SYSTEM, content, **kwargs)

    def add_agent_message(
        self,
        content: str,
        agent_name: str,
        *,
        status: MessageStatus = MessageStatus.DONE,
        attachments: list[Attachment] | None = None,
        needs_reply: bool = False,
        **kwargs,
    ) -> Message:
        return self.add_message(
            MessageRole.AGENT,
            content,
            agent_name=agent_name,
            status=status,
            attachments=attachments,
            needs_reply=needs_reply,
            **kwargs,
        )

    def update_agent_state(self, agent_name: str, status: MessageStatus) -> None:
        self.agent_states[agent_name] = status
        self.updated_at = time.time()

    def get_agent_state(self, agent_name: str) -> MessageStatus:
        return self.agent_states.get(agent_name, MessageStatus.IDLE)

    def get_last_user_message(self) -> Message | None:
        for m in reversed(self.messages):
            if m.role == MessageRole.USER:
                return m
        return None

    def get_last_agent_message(self, agent_name: str) -> Message | None:
        for m in reversed(self.messages):
            if m.role == MessageRole.AGENT and m.agent_name == agent_name:
                return m
        return None

    def get_context(self, max_messages: int = 20) -> list[dict[str, Any]]:
        return [
            {
                "role": m.role.value,
                "content": m.content,
                "agent_name": m.agent_name,
                "phase": m.phase,
            }
            for m in self.messages[-max_messages:]
        ]

    @classmethod
    def create_welcome_session(cls) -> ChatSession:
        session = cls(id=f"session_{int(time.time())}")
        session.add_system_message(
            "**به استودیوی انیمیشن خوش آمدید!**\n\n"
            "من یک تیم از ایجنت‌های متخصص را مدیریت می‌کنم. "
            "کافیست بگویید چه انیمیشنی می‌خواهید بسازید.\n\n"
            "🖼 **آپلود کاراکتر (اختیاری):**\n"
            "اگر عکس کاراکتر دارید، از دکمه آپلود در پایین صفحه استفاده کنید "
            "یا بعداً با دستور `/character` می‌توانید وضعیت را ببینید.\n\n"
            "**دستورات:**\n"
            "- `/agents` — لیست ایجنت‌های موجود\n"
            "- `/character` — وضعیت و آپلود کاراکتر\n"
            "- `/run` — اجرای خودکار همه ایجنت‌ها\n"
            "- `/agent <name>` — صدا زدن یک ایجنت خاص\n"
            "- `/code` — نمایش آخرین کد خروجی\n"
            "- `/export` — دانلود پروژه",
            phase="welcome",
        )
        return session

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "brief": self.brief,
            "current_phase": self.current_phase,
            "quality": self.quality,
            "approved": self.approved,
            "exported": self.exported,
            "rendered": self.rendered,
            "agent_states": {k: v.value for k, v in self.agent_states.items()},
            "messages": [
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "agent_name": m.agent_name,
                    "status": m.status.value,
                    "attachments": [
                        {
                            "type": a.type,
                            "label": a.label,
                            "content": a.content,
                            "language": a.language,
                        }
                        for a in m.attachments
                    ],
                    "needs_reply": m.needs_reply,
                    "suggestions": m.suggestions,
                    "phase": m.phase,
                    "error": m.error,
                    "timestamp": m.timestamp,
                }
                for m in self.messages[-100:]
            ],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> ChatSession:
        if not path.is_file():
            return cls.create_welcome_session()
        data = json.loads(path.read_text(encoding="utf-8"))
        session = cls(
            id=data.get("id", f"session_{int(time.time())}"),
            brief=data.get("brief", ""),
            current_phase=data.get("current_phase", "idle"),
            quality=data.get("quality", "light"),
            approved=data.get("approved", False),
            exported=data.get("exported", False),
            rendered=data.get("rendered", False),
            metadata=data.get("metadata", {}),
            agent_states={
                k: MessageStatus(v)
                for k, v in data.get("agent_states", {}).items()
            },
        )
        for m in data.get("messages") or []:
            session.messages.append(Message(
                id=m.get("id", make_message_id()),
                role=MessageRole(m.get("role", "system")),
                content=m.get("content", ""),
                agent_name=m.get("agent_name", ""),
                status=MessageStatus(m.get("status", "idle")),
                attachments=[
                    Attachment(**a) for a in m.get("attachments") or []
                ],
                needs_reply=m.get("needs_reply", False),
                suggestions=m.get("suggestions", []),
                phase=m.get("phase", ""),
                error=m.get("error"),
                timestamp=m.get("timestamp", time.time()),
            ))
        return session
