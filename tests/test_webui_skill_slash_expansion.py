"""WebUI should expand standalone skill slash commands like CLI/gateway."""

from types import ModuleType


def test_webui_expands_standalone_skill_slash_message(monkeypatch):
    import sys
    import api.streaming as streaming

    agent_pkg = ModuleType("agent")
    agent_pkg.__path__ = []
    skill_commands = ModuleType("agent.skill_commands")

    def resolve_skill_command_key(command):
        assert command == "build-tear-sheet"
        return "/build-tear-sheet"

    def build_skill_invocation_message(cmd_key, user_instruction, task_id=None):
        assert cmd_key == "/build-tear-sheet"
        assert user_instruction == "microsoft"
        assert task_id == "session-1"
        return "EXPANDED SKILL CONTENT"

    skill_commands.resolve_skill_command_key = resolve_skill_command_key
    skill_commands.build_skill_invocation_message = build_skill_invocation_message
    monkeypatch.setitem(sys.modules, "agent", agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.skill_commands", skill_commands)

    assert (
        streaming._expand_webui_skill_slash_message(
            "/build-tear-sheet microsoft",
            task_id="session-1",
        )
        == "EXPANDED SKILL CONTENT"
    )


def test_webui_leaves_non_skill_slash_message_unchanged(monkeypatch):
    import sys
    import api.streaming as streaming

    agent_pkg = ModuleType("agent")
    agent_pkg.__path__ = []
    skill_commands = ModuleType("agent.skill_commands")
    skill_commands.resolve_skill_command_key = lambda _command: None
    skill_commands.build_skill_invocation_message = lambda *_args, **_kwargs: "unused"
    monkeypatch.setitem(sys.modules, "agent", agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.skill_commands", skill_commands)

    assert streaming._expand_webui_skill_slash_message("/help") == "/help"
