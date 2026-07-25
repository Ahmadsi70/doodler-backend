"""Tests for the new chat-centric system."""
from __future__ import annotations

from chat.chat_session import ChatSession
from chat.message_types import Message, MessageRole, MessageStatus, Attachment
from chat.agent_bus import AgentBus, AgentMode


class TestMessageTypes:
    def test_message_creation(self):
        msg = Message(
            id="test_1",
            role=MessageRole.USER,
            content="Hello",
        )
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.status == MessageStatus.IDLE

    def test_message_with_attachment(self):
        att = Attachment(
            type="code",
            label="test.tsx",
            content="const x = 1;",
            language="typescript",
        )
        msg = Message(
            id="test_2",
            role=MessageRole.AGENT,
            content="Code:",
            agent_name="RenderAgent",
            attachments=[att],
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0].language == "typescript"
        assert msg.agent_name == "RenderAgent"


class TestChatSession:
    def test_create_welcome_session(self):
        session = ChatSession.create_welcome_session()
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.SYSTEM
        assert session.messages[0].phase == "welcome"

    def test_add_user_message(self):
        session = ChatSession.create_welcome_session()
        msg = session.add_user_message("یک انیمیشن بساز")
        assert msg.role == MessageRole.USER
        assert msg.content == "یک انیمیشن بساز"
        assert len(session.messages) == 2

    def test_add_agent_message(self):
        session = ChatSession.create_welcome_session()
        msg = session.add_agent_message(
            "فیلمنامه آماده است",
            agent_name="DraftScreenplay",
            status=MessageStatus.DONE,
            needs_reply=True,
            suggestions=["تأیید", "ویرایش"],
        )
        assert msg.role == MessageRole.AGENT
        assert msg.agent_name == "DraftScreenplay"
        assert msg.needs_reply is True
        assert len(msg.suggestions) == 2

    def test_agent_state_tracking(self):
        session = ChatSession.create_welcome_session()
        assert session.get_agent_state("DraftScreenplay") == MessageStatus.IDLE
        session.update_agent_state("DraftScreenplay", MessageStatus.WORKING)
        assert session.get_agent_state("DraftScreenplay") == MessageStatus.WORKING
        session.update_agent_state("DraftScreenplay", MessageStatus.DONE)
        assert session.get_agent_state("DraftScreenplay") == MessageStatus.DONE

    def test_get_last_user_message(self):
        session = ChatSession.create_welcome_session()
        session.add_user_message("اولین")
        session.add_user_message("دومین")
        last = session.get_last_user_message()
        assert last is not None
        assert last.content == "دومین"

    def test_get_context(self):
        session = ChatSession.create_welcome_session()
        session.add_user_message("سلام")
        session.add_agent_message("خوش آمدی", agent_name="System")
        context = session.get_context(max_messages=10)
        assert len(context) == 3
        assert context[-2]["role"] == "user"
        assert context[-1]["role"] == "agent"

    def test_save_load_roundtrip(self, tmp_path):
        session = ChatSession.create_welcome_session()
        session.add_user_message("تست")
        session.add_agent_message("پاسخ", agent_name="Agent")
        session.brief = "تست brief"

        path = tmp_path / "session.json"
        session.save(path)
        assert path.is_file()

        loaded = ChatSession.load(path)
        assert loaded.brief == "تست brief"
        assert len(loaded.messages) == len(session.messages)
        assert loaded.messages[-1].content == "پاسخ"
        assert loaded.messages[-1].agent_name == "Agent"


class TestAgentBus:
    def test_register_and_list(self):
        bus = AgentBus()

        async def dummy_handler(input: str, session: ChatSession):
            return [{"type": "done"}]

        bus.register("Agent1", "First agent", dummy_handler, phase="a")
        bus.register("Agent2", "Second agent", dummy_handler, phase="b")
        bus.register(
            "Agent3", "Third agent", dummy_handler,
            phase="c", dependencies=["Agent1"], mode=AgentMode.MANUAL,
        )

        agents = bus.list_agents()
        assert len(agents) == 3
        assert agents[0]["name"] == "Agent1"
        assert agents[2]["mode"] == "manual"

    def test_get_agents_by_phase(self):
        bus = AgentBus()

        async def handler(input: str, session: ChatSession):
            return []

        bus.register("A1", "desc", handler, phase="alpha")
        bus.register("A2", "desc", handler, phase="beta")
        bus.register("A3", "desc", handler, phase="alpha")

        alpha_agents = bus.get_agents_by_phase("alpha")
        assert len(alpha_agents) == 2
        assert [a.name for a in alpha_agents] == ["A1", "A3"]

    def test_dependency_ordering(self):
        bus = AgentBus()

        async def handler(input: str, session: ChatSession):
            return []

        bus.register("Render", "Render", handler, dependencies=["Camera", "Timing"])
        bus.register("Camera", "Camera", handler, dependencies=["Storyboard"])
        bus.register("Storyboard", "Storyboard", handler)
        bus.register("Timing", "Timing", handler, dependencies=["Storyboard"])

        order = bus.get_dependency_order()
        names = [a.name for a in order]
        # Storyboard must come before all others
        assert names.index("Storyboard") < names.index("Camera")
        assert names.index("Storyboard") < names.index("Timing")
        assert names.index("Storyboard") < names.index("Render")

    def test_unregister(self):
        bus = AgentBus()

        async def handler(input: str, session: ChatSession):
            return []

        bus.register("Temp", "Temporary", handler)
        assert len(bus.list_agents()) == 1
        bus.unregister("Temp")
        assert len(bus.list_agents()) == 0

    def test_get_nonexistent_agent(self):
        bus = AgentBus()
        assert bus.get_agent("Ghost") is None

    def test_frame_pipeline_registration(self):
        bus = AgentBus()

        async def dummy_handler(input: str, session: ChatSession):
            return [{"type": "done"}]

        bus.register("FramePipeline", "Frame pipeline", dummy_handler,
                     phase="frame_details", dependencies=["Continuity"], mode=AgentMode.AUTO)
        bus.register("ArtDirector", "Art director", dummy_handler,
                     phase="art_director", dependencies=["Storyboard"], mode=AgentMode.MANUAL)

        agents = {a["name"]: a for a in bus.list_agents()}
        assert "FramePipeline" in agents
        assert agents["FramePipeline"]["phase"] == "frame_details"
        assert agents["FramePipeline"]["dependencies"] == ["Continuity"]
        assert agents["FramePipeline"]["mode"] == "auto"

        assert "ArtDirector" in agents
        assert agents["ArtDirector"]["phase"] == "art_director"
        assert agents["ArtDirector"]["dependencies"] == ["Storyboard"]
        assert agents["ArtDirector"]["mode"] == "manual"

    def test_art_director_agent_module(self):
        from agents.art_director_agent import run_art_director_agent

        storyboard = {
            "shots": [
                {
                    "shot_id": 0,
                    "action": "Hero enters the room",
                    "story_beat": "entrance",
                    "composition_shape": "C",
                    "shot_size": "MS",
                    "lighting": "three_point",
                    "camera": "static",
                    "lens": "standard",
                }
            ]
        }
        result = run_art_director_agent(
            storyboard,
            character_description="tall warrior with long black hair, green eyes",
            style_id="cinematic",
        )
        assert result["schema"] == "art_director#v1"
        assert result["style_id"] == "cinematic"
        assert len(result["shots"]) == 1
        shot = result["shots"][0]
        assert shot["shotId"] == 0
        assert "midjourney" in shot["prompts"]
        assert "sdxl" in shot["prompts"]
        assert "dalle3" in shot["prompts"]
        assert "character_seed" in shot
        assert shot["character_seed"] > 0

    def test_frame_pipeline_build_chart_input(self):
        from agents.frame_pipeline import build_chart_input

        shots = [
            {
                "shotId": 0,
                "action": "Hero walks in",
                "storyBeat": "entrance",
                "craftHints": {"rig": {"pose": "walk", "expression": "neutral"}},
                "durationFrames": 72,
                "anticipationFrames": 6,
                "holdFrames": 12,
                "camera": "static",
                "cameraMove": {"id": "static"},
            }
        ]
        chart = build_chart_input(shots)
        assert len(chart) == 1
        assert chart[0]["shot_id"] == 0
        assert chart[0]["pose"] == "walk"
        assert chart[0]["camera"] == "static"

    def test_full_agent_registration_count(self):
        from agents.chat_agent_wrapper import register_all_agents

        bus = AgentBus()
        register_all_agents(bus)
        agents = bus.list_agents()
        assert len(agents) == 10  # DraftScreenplay + ScriptBreakdown + Storyboard + Cinematography + AnimationTiming + Continuity + FramePipeline + RenderAgent + ArtDirector + RubberDuck
        names = [a["name"] for a in agents]
        assert "FramePipeline" in names
        assert "ArtDirector" in names
        assert "RubberDuck" in names
        assert "RenderAgent" in names
