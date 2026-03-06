"""Load heartbeat config: HEARTBEAT.md (private) or HEARTBEAT.example.md (template).

HEARTBEAT.md is gitignored — your private config. The repo ships HEARTBEAT.example.md
as the template. If HEARTBEAT.md exists, use it; else use HEARTBEAT.example.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

HEARTBEAT_OK_RESPONSE = "HEARTBEAT_OK"


def load_heartbeat_config() -> str:
    """Load heartbeat config: HEARTBEAT.md if present, else HEARTBEAT.example.md.

    Returns:
        Markdown string for use as system/instruction context.
    """
    base_path = Path(settings.heartbeat_md_path)
    parent = base_path.parent
    stem, suffix = base_path.stem, base_path.suffix
    example_path = parent / (stem + ".example" + suffix)

    if base_path.exists():
        config_path = base_path
        logger.debug("Using private HEARTBEAT.md")
    elif example_path.exists():
        config_path = example_path
        logger.debug("No HEARTBEAT.md — using HEARTBEAT.example.md template")
    else:
        logger.warning(
            "No HEARTBEAT.md or HEARTBEAT.example.md at %s / %s — heartbeat will use minimal context",
            base_path,
            example_path,
        )
        return "Respond with HEARTBEAT_OK if nothing warrants contacting the user.\n"

    try:
        return config_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Could not read %s: %s", config_path, e)
        return "Respond with HEARTBEAT_OK if nothing warrants contacting the user.\n"
