"""Setup helpers — env→extra seeding, YAML→env bridge, interactive wizard."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ._env import env


DEFAULT_SERVER_URL = "wss://claw-messenger.onrender.com"
DEFAULT_PREFERRED_SERVICE = "iMessage"


def env_enablement() -> Optional[Dict[str, Any]]:
    """Seed PlatformConfig.extra (and home_channel) from env vars.

    Returning ``None`` tells Hermes the plugin is not configured. Returning a
    dict makes the plugin show up in ``hermes gateway status`` without
    instantiating the adapter.
    """
    if not env("CLAW_MESSENGER_API_KEY"):
        return None
    extra: Dict[str, Any] = {
        "server_url": env("CLAW_MESSENGER_SERVER_URL", DEFAULT_SERVER_URL),
        "preferred_service": env(
            "CLAW_MESSENGER_PREFERRED_SERVICE", DEFAULT_PREFERRED_SERVICE
        ),
    }
    home_channel_id = env("CLAW_MESSENGER_HOME_CHANNEL")
    result: Dict[str, Any] = {"extra": extra}
    if home_channel_id:
        result["home_channel"] = {"chat_id": home_channel_id}
    return result


def apply_yaml_config(yaml_cfg, platform_cfg) -> Optional[Dict[str, Any]]:
    """Bridge ``gateway.platforms.claw_messenger`` keys in config.yaml → env vars."""
    if not isinstance(yaml_cfg, dict):
        return None

    set_env = _yaml_env_setter()
    extra: Dict[str, Any] = {}
    yaml_to_env = {
        "api_key": "CLAW_MESSENGER_API_KEY",
        "server_url": "CLAW_MESSENGER_SERVER_URL",
        "preferred_service": "CLAW_MESSENGER_PREFERRED_SERVICE",
        "home_channel": "CLAW_MESSENGER_HOME_CHANNEL",
        "allowed_users": "CLAW_MESSENGER_ALLOWED_USERS",
        "allow_all_users": "CLAW_MESSENGER_ALLOW_ALL_USERS",
    }
    for yaml_key, env_name in yaml_to_env.items():
        if yaml_key not in yaml_cfg:
            continue
        val = yaml_cfg[yaml_key]
        if val is None:
            continue
        if isinstance(val, list):
            val = ",".join(str(x) for x in val)
        elif isinstance(val, bool):
            val = "true" if val else "false"
        set_env(env_name, val)
        extra[yaml_key] = val
    return extra or None


def _yaml_env_setter():
    """Hermes's YAML-to-env writer: explicit env wins, and nothing is written while a
    multiplexed secondary profile's config loads (that would hand its API key to the
    default profile). The values still go into ``extra``, so each profile's adapter
    reads its own. Outside Hermes, write only unset vars."""
    try:
        from gateway.platforms._shared import yaml_env_setter
    except ImportError:
        def set_env(name: str, value: Any) -> None:
            if not os.getenv(name):
                os.environ[name] = str(value)
        return set_env
    return yaml_env_setter()


def interactive_setup(*args, **kwargs) -> bool:
    """Walk a user through configuring the plugin.

    Called by ``hermes gateway setup``. Signature is intentionally flexible —
    Hermes versions have evolved this contract over time; we accept whatever it
    passes and look for the ``console`` and ``env_path`` we need.
    """
    console = kwargs.get("console") or (args[0] if args else None)
    env_path = kwargs.get("env_path") or (args[1] if len(args) > 1 else None)

    def out(msg: str) -> None:
        if console is not None and hasattr(console, "print"):
            console.print(msg)
        else:
            print(msg)

    out("[bold]Claw Messenger setup[/bold]")
    out("1. Sign up at https://clawmessenger.com")
    out("2. Generate an API key from the dashboard.")
    try:
        api_key = input("API key (cm_live_…): ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if not api_key.startswith("cm_live_"):
        out("[yellow]Key doesn't look right — expected to start with cm_live_[/yellow]")
        return False

    try:
        service = (input(f"Preferred service [{DEFAULT_PREFERRED_SERVICE}]/RCS/SMS: ").strip()
                   or DEFAULT_PREFERRED_SERVICE)
        home = input("Home channel for cron (E.164 or chatId, blank to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    values = {
        "CLAW_MESSENGER_API_KEY": api_key,
        "CLAW_MESSENGER_PREFERRED_SERVICE": service,
        **({"CLAW_MESSENGER_HOME_CHANNEL": home} if home else {}),
    }
    if env_path is None:
        # Hermes owns ~/.hermes/.env (profiles, export lines, write guards).
        from hermes_cli.config import save_env_value
        for key, value in values.items():
            save_env_value(key, value)
    else:
        _append_env_lines(env_path, values)
    out("[green]✓ Claw Messenger configured.[/green]")
    out("[dim]Next: register phone numbers via the dashboard or the /api/phone-routes endpoint.[/dim]")
    return True


def _append_env_lines(env_path, values: Dict[str, str]) -> None:
    from pathlib import Path

    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = env_path.read_text() if env_path.exists() else ""

    # Strip any prior settings of the same keys so we don't accumulate dupes.
    lines = existing.splitlines()
    kept = [line for line in lines if not any(line.startswith(f"{k}=") for k in values)]
    kept.extend(f"{k}={v}" for k, v in values.items())
    env_path.write_text("\n".join(kept) + "\n")
