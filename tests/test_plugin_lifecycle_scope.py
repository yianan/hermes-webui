"""Plugin mutations release the Agent profile scope even after a refusal."""
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.parametrize("refused", [False, True])
def test_current_profile_is_bound_and_released(monkeypatch, refused):
    from api import plugin_lifecycle, profiles

    home = Path("/tmp/fixture-profile")
    marker = object()
    events = []
    runtime = ModuleType("tui_gateway.model_switch")
    runtime._profile_runtime_scope_tokens = lambda path: events.append(("bind", path)) or marker
    runtime._release_profile_runtime_scope_tokens = lambda token: events.append(("release", token))
    package = ModuleType("tui_gateway")
    package.model_switch = runtime
    monkeypatch.setitem(sys.modules, "tui_gateway", package)
    monkeypatch.setitem(sys.modules, "tui_gateway.model_switch", runtime)
    monkeypatch.setattr(profiles, "get_active_hermes_home", lambda: home)

    def operate():
        with plugin_lifecycle.active_plugin_runtime_scope():
            events.append(("operation", home))
            if refused:
                raise ValueError("admission refused")

    if refused:
        with pytest.raises(ValueError, match="admission refused"):
            operate()
    else:
        operate()
    assert events == [("bind", home), ("operation", home), ("release", marker)]
