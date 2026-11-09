"""YAML config bridge must not leak one profile's settings into another."""

from __future__ import annotations

import os

from hermes_claw_messenger.setup import apply_yaml_config


def test_yaml_bridge_never_writes_env_inside_a_secondary_profile(monkeypatch):
    from agent.secret_scope import reset_secret_scope, set_multiplex_context, set_secret_scope

    monkeypatch.delenv("CLAW_MESSENGER_API_KEY", raising=False)
    mux = set_multiplex_context(True)
    scope = set_secret_scope({}, profile_home="/profiles/b")
    try:
        extra = apply_yaml_config({"api_key": "cm_live_B"}, {})
    finally:
        reset_secret_scope(scope)
        from agent.secret_scope import reset_multiplex_context
        reset_multiplex_context(mux)
    assert extra == {"api_key": "cm_live_B"}
    assert "CLAW_MESSENGER_API_KEY" not in os.environ


def test_yaml_bridge_fills_unset_env_for_the_default_profile(monkeypatch):
    monkeypatch.delenv("CLAW_MESSENGER_PREFERRED_SERVICE", raising=False)
    extra = apply_yaml_config({"preferred_service": "SMS"}, {})
    assert extra == {"preferred_service": "SMS"}
    assert os.environ["CLAW_MESSENGER_PREFERRED_SERVICE"] == "SMS"
    monkeypatch.delenv("CLAW_MESSENGER_PREFERRED_SERVICE", raising=False)
