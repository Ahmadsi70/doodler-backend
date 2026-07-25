from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    RUBBER_DUCK = "rubber_duck"


class MessageStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    AWAITING_INPUT = "awaiting_input"
    DONE = "done"
    ERROR = "error"


@dataclass
class Attachment:
    type: Literal["code", "image", "json", "file", "markdown"]
    label: str
    content: str
    language: str | None = None


@dataclass
class Message:
    id: str = ""
    role: MessageRole = MessageRole.SYSTEM
    content: str = ""
    agent_name: str = ""
    status: MessageStatus = MessageStatus.IDLE
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    attachments: list[Attachment] = field(default_factory=list)
    needs_reply: bool = False
    suggestions: list[str] = field(default_factory=list)
    phase: str = ""
    error: str | None = None


@dataclass
class AgentMessage(Message):
    role: MessageRole = MessageRole.AGENT
    agent_name: str = ""
    status: MessageStatus = MessageStatus.WORKING
    progress: float = 0.0


def make_message_id() -> str:
    return f"msg_{int(time.time() * 1000)}_{id({})}"
