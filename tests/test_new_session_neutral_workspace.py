"""Regression coverage for generic New Chat workspace binding."""

from pathlib import Path


def test_backend_new_session_without_workspace_uses_profile_default(monkeypatch):
    import api.models as models

    monkeypatch.setattr(models, "get_last_workspace", lambda: "/tmp/demo-last-workspace")
    monkeypatch.setattr(models, "get_neutral_default_workspace", lambda: "/tmp/neutral-profile-default")

    session = models.new_session(workspace=None, model="gpt-test", profile="default")

    assert Path(session.workspace).resolve() == Path("/tmp/neutral-profile-default").resolve()
