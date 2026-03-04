"""Calendar tool executors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import ToolRegistry

logger = logging.getLogger(__name__)


async def exec_calendar_events(registry: ToolRegistry, inp: dict) -> str:
    """List upcoming Google Calendar events."""
    if registry._calendar is None:
        return (
            "Google Calendar not configured. "
            "Run scripts/setup_google_auth.py to set it up."
        )
    days = min(int(inp.get("days", 7)), 30)
    err: Exception | None = None
    try:
        events = await registry._calendar.list_events(days=days)
    except Exception as e:
        err = e
    if err is not None:
        return f"Could not fetch calendar events: {err}"

    if not events:
        period = "today" if days == 1 else f"the next {days} days"
        return f"No events scheduled for {period}."

    lines = [f"Calendar events (next {days} day{'s' if days != 1 else ''}):"]
    for ev in events:
        lines.append(registry._calendar.format_event(ev))
    return "\n".join(lines)


async def exec_create_calendar_event(registry: ToolRegistry, inp: dict) -> str:
    """Create a new event on Google Calendar."""
    if registry._calendar is None:
        return (
            "Google Calendar not configured. "
            "Run scripts/setup_google_auth.py to set it up."
        )
    title = inp.get("title", "").strip()
    date = inp.get("date", "").strip()
    time = inp.get("time", "").strip()
    duration = float(inp.get("duration_hours", 1.0))
    description = inp.get("description", "").strip()

    if not title or not date or not time:
        return "Cannot create event: title, date, and time are all required."

    err: Exception | None = None
    try:
        event = await registry._calendar.create_event(
            title, date, time, duration, description
        )
    except ValueError as e:
        err = e
        return f"Invalid date/time: {err}"
    except Exception as e:
        err = e
        return f"Failed to create calendar event: {err}"

    link = event.get("htmlLink", "")
    return (
        f"✅ Calendar event created: {title}\n"
        f"Date: {date} at {time} ({duration}h)\n"
        f"Link: {link}"
    )
