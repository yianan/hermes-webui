"""WebUI resolves the selected PM generation, rather than the retired venv."""
import json
from pathlib import Path
import shlex
import sys

import bootstrap


def test_managed_python_is_selected_without_importing_the_agent(tmp_path, monkeypatch):
    root = tmp_path / "agent"
    launcher = root / ".hermes/bin/hermes"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(json.dumps([sys.executable])) + "\n")
    launcher.chmod(0o700)
    selected = root / "generation/bin/python"
    selected.parent.mkdir(parents=True)
    selected.symlink_to(sys.executable)
    package = root / "pm"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "environments.py").write_text("def project_python(root): return root / 'generation/bin/python'\n")
    (root / "run_agent.py").write_text("raise RuntimeError('must not import Agent while selecting Python')\n")
    monkeypatch.delenv("HERMES_WEBUI_PYTHON", raising=False)
    assert bootstrap.discover_launcher_python(root) == str(selected)


def test_explicit_python_override_is_authoritative(monkeypatch):
    monkeypatch.setenv("HERMES_WEBUI_PYTHON", "/tmp/explicit-python")
    monkeypatch.setattr(bootstrap, "_managed_agent_python", lambda root: (_ for _ in ()).throw(AssertionError()))
    assert bootstrap.discover_launcher_python(Path("/tmp/agent")) == "/tmp/explicit-python"
