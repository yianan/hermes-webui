"""Profile-isolation coverage for the local Gmail watcher controls."""

import json

from api import service_control


def test_watcher_status_uses_active_profile_and_webui_state(monkeypatch, tmp_path):
    hermes_home = tmp_path / "profile"
    webui_state = tmp_path / "webui-state"
    script_state = hermes_home / "scripts" / "state"
    log_dir = hermes_home / "logs"
    session_dir = webui_state / "sessions"
    script_state.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    session_dir.mkdir(parents=True)
    (script_state / "gmail_keyword_seen.txt").write_text("a\nb\n", encoding="utf-8")
    (log_dir / "gmail-keyword-watcher.log").write_text("watcher line\n", encoding="utf-8")
    (session_dir / "gmail_keyword_watcher.json").write_text(
        json.dumps({"messages": [{"role": "assistant", "content": "match"}]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(service_control, "_active_hermes_home", lambda: hermes_home)
    monkeypatch.setattr(service_control, "_gateway_running", lambda: False)
    monkeypatch.setenv("HERMES_WEBUI_STATE_DIR", str(webui_state))

    status = service_control.gmail_watcher_status()

    assert status["config_path"] == str(hermes_home / "scripts" / "gmail_keyword_watcher.json")
    assert status["seen_path"] == str(script_state / "gmail_keyword_seen.txt")
    assert status["seen_count"] == 2
    assert status["log_path"] == str(log_dir / "gmail-keyword-watcher.log")
    assert status["log_tail"] == ["watcher line"]
    assert status["recent_alerts"] == [
        {"role": "assistant", "timestamp": None, "content": "match"}
    ]
