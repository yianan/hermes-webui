"""Bind the current WebUI profile before invoking Agent plugin mutations."""
from contextlib import contextmanager


@contextmanager
def active_plugin_runtime_scope():
    from api.profiles import get_active_hermes_home
    from tui_gateway.model_switch import (
        _profile_runtime_scope_tokens,
        _release_profile_runtime_scope_tokens,
    )

    scopes = _profile_runtime_scope_tokens(get_active_hermes_home())
    try:
        yield
    finally:
        _release_profile_runtime_scope_tokens(scopes)
