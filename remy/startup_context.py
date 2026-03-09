"""
Late-bound startup dependencies.

Phase 1.5: Replaces the _late dict with a typed dataclass.
Supports dict-like .get() for scheduler_ref compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StartupContext:
    """Late-bound startup dependencies. Supports dict-like .get() for scheduler_ref compatibility."""

    proactive_scheduler = None
    diagnostics_runner = None
    bot = None
    outbound_queue: object = (
        None  # Injected at construction; late-bound items use default None
    )

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __setitem__(self, key: str, value) -> None:
        setattr(self, key, value)
