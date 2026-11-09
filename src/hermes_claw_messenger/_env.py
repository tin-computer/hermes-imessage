"""Settings and credentials, read through Hermes.

Hermes resolves credentials per profile (``agent.secret_scope.get_secret``), so a
plugin must not read ``os.environ`` for them directly: under profile
multiplexing that could pick up another profile's key. Outside Hermes (the
standalone tests, a bare Python shell) we fall back to the process environment.
"""

from __future__ import annotations

import os
from typing import Optional


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return os.getenv(name, default)
    return get_secret(name, default)
