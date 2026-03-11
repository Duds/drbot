"""
Late-bound startup dependencies.

Phase 1.5: Replaces the _late dict with a typed dataclass.
Supports dict-like .get() for scheduler_ref compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


@dataclass
class StartupContext:
    """Late-bound startup dependencies. Supports dict-like .get() for scheduler_ref compatibility."""

    outbound_queue: Any = None
    proactive_scheduler: Any = None
    diagnostics_runner: Any = None
    bot: Any = None

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __setitem__(self, key: str, value) -> None:
        setattr(self, key, value)
