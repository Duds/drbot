"""Utilities for parsing JSON from Claude's responses."""

from __future__ import annotations


def strip_code_fences(text: str) -> str:
    """
    Strip markdown code fences from a Claude response that should be plain JSON.

    Claude sometimes wraps JSON in ```json ... ``` or ``` ... ``` fences.
    This strips them so the result can be parsed by json.loads().
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence line (e.g., "```json" or "```")
        cleaned = cleaned.split("\n", 1)[-1]
        # Drop the closing fence
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()
