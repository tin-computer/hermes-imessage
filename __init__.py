"""Hermes directory-plugin entry point (used by `hermes plugins install claw-messenger`).

The plugin's code lives in src/hermes_claw_messenger, which is also what the
PyPI package (`hermes-imessage`) ships. This file only re-exports its
register() so a checkout of this repository loads as a directory plugin.
"""

from .src.hermes_claw_messenger import register  # noqa: F401
