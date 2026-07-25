from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from .message_types import Attachment, MessageRole, MessageStatus
from .chat_session import ChatSession


class AgentMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


AgentHandler = Callable[[str, ChatSession], Coroutine[Any, Any, list[dict[str, Any]]]]


@dataclass
class AgentRegistration:
    name: str
    description: str
    handler: AgentHandler
    phase: str = ""
    dependencies: list[str] = field(default_factory=list)
    mode: AgentMode = AgentMode.AUTO
    enabled: bool = True


class AgentBus:
    def __init__(self):
        self._agents: dict[str, AgentRegistration] = {}
        self._on_message_callbacks: list[Callable[[dict[str, Any]], None]] = []

    def register(
        self,
        name: str,
        description: str,
        handler: AgentHandler,
        *,
        phase: str = "",
        dependencies: list[str] | None = None,
        mode: AgentMode = AgentMode.AUTO,
    ) -> None:
        self._agents[name] = AgentRegistration(
            name=name,
            description=description,
            handler=handler,
            phase=phase,
            dependencies=dependencies or [],
            mode=mode,
        )

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def get_agent(self, name: str) -> AgentRegistration | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "name": a.name,
                "description": a.description,
                "phase": a.phase,
                "dependencies": a.dependencies,
                "mode": a.mode.value,
                "enabled": a.enabled,
            }
            for a in self._agents.values()
        ]

    def get_agents_by_phase(self, phase: str) -> list[AgentRegistration]:
        return [a for a in self._agents.values() if a.phase == phase and a.enabled]

    def get_auto_agents(self) -> list[AgentRegistration]:
        return [
            a for a in self._agents.values()
            if a.mode == AgentMode.AUTO and a.enabled
        ]

    def get_dependency_order(self) -> list[AgentRegistration]:
        resolved: list[str] = []
        visited: set[str] = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            agent = self._agents.get(name)
            if agent is None:
                return
            for dep in agent.dependencies:
                dfs(dep)
            if name not in resolved:
                resolved.append(name)

        for name in self._agents:
            dfs(name)

        return [self._agents[name] for name in resolved if self._agents[name].enabled]

    async def run_agent(
        self,
        name: str,
        user_input: str,
        session: ChatSession,
    ) -> list[dict[str, Any]]:
        agent = self._agents.get(name)
        if agent is None:
            return [{"type": "error", "content": f"Agent '{name}' not found"}]

        if not agent.enabled:
            return [{"type": "error", "content": f"Agent '{name}' is disabled"}]

        session.update_agent_state(name, MessageStatus.WORKING)
        self._broadcast({
            "type": "agent_start",
            "agent": name,
            "session_id": session.id,
            "timestamp": time.time(),
        })

        try:
            result = await agent.handler(user_input, session)
            session.update_agent_state(name, MessageStatus.DONE)
            self._broadcast({
                "type": "agent_done",
                "agent": name,
                "session_id": session.id,
                "timestamp": time.time(),
            })
            return result
        except Exception as e:
            session.update_agent_state(name, MessageStatus.ERROR)
            error_msg = str(e)
            session.add_agent_message(
                f"خطا در اجرای {name}: {error_msg}",
                agent_name=name,
                status=MessageStatus.ERROR,
                error=error_msg,
            )
            self._broadcast({
                "type": "agent_error",
                "agent": name,
                "session_id": session.id,
                "error": error_msg,
                "timestamp": time.time(),
            })
            return [{"type": "error", "content": error_msg}]

    async def run_auto_pipeline(
        self,
        user_input: str,
        session: ChatSession,
    ) -> list[dict[str, Any]]:
        # Inject character description into pipeline context
        char_desc = session.metadata.get("character_description", "")
        enriched_input = user_input
        if char_desc:
            enriched_input = (
                f"{user_input}\n\n"
                f"---\n"
                f"**ویژگی‌های کاراکتر:**\n{char_desc}\n"
                f"---"
            )
        session.brief = enriched_input
        results: list[dict[str, Any]] = []
        ordered = self.get_dependency_order()

        for agent in ordered:
            if not agent.enabled or agent.mode != AgentMode.AUTO:
                continue

            agent_result = await self.run_agent(agent.name, enriched_input, session)
            results.extend(agent_result)

        return results

    def on_message(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._on_message_callbacks.append(callback)

    def _broadcast(self, event: dict[str, Any]) -> None:
        for cb in self._on_message_callbacks:
            try:
                cb(event)
            except Exception:
                pass
