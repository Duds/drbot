"""
Google Calendar handlers.

Contains handlers for calendar operations: viewing events and creating events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .base import reject_unauthorized, google_not_configured

if TYPE_CHECKING:
    from ...google.calendar import CalendarClient

logger = logging.getLogger(__name__)


def make_calendar_handlers(
    *,
    google_calendar: "CalendarClient | None" = None,
):
    """
    Factory that returns Google Calendar handlers.

    Returns a dict of command_name -> handler_function.
    """

    async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/calendar [days=7] — list upcoming calendar events."""
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        if google_calendar is None:
            await update.message.reply_text(google_not_configured("Calendar"))
            return
        try:
            days = int(context.args[0]) if context.args else 7
            days = max(1, min(days, 30))
        except (ValueError, IndexError):
            days = 7
        await update.message.reply_text("📅 Fetching calendar…")
        err: Exception | None = None
        try:
            events = await google_calendar.list_events(days=days)
        except Exception as exc:
            err = exc
        if err is not None:
            await update.message.reply_text(f"❌ Calendar error: {err}")
            return
        if not events:
            await update.message.reply_text(f"📅 No events in the next {days} day(s).")
            return
        lines = [f"📅 *Next {days} day(s):*"]
        prev_date = None
        for ev in events:
            start = ev.get("start", {})
            dt_str = start.get("dateTime", start.get("date", ""))
            date_part = dt_str[:10] if dt_str else ""
            if date_part != prev_date:
                lines.append(f"\n_{date_part}_")
                prev_date = date_part
            lines.append(google_calendar.format_event(ev))
        msg = "\n".join(lines)
        if len(msg) > 4000:
            msg = msg[:4000] + "…"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def calendar_today_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """/calendar-today — today's events at a glance."""
        context.args = ["1"]
        await calendar_command(update, context)

    async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/schedule <title> <YYYY-MM-DD> <HH:MM> — create a calendar event (1-hour block)."""
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        if google_calendar is None:
            await update.message.reply_text(google_not_configured("Calendar"))
            return
        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /schedule <title> <YYYY-MM-DD> <HH:MM>\n"
                "Example: /schedule Team standup 2026-03-01 09:00"
            )
            return
        date_str = context.args[-2]
        time_str = context.args[-1]
        title = " ".join(context.args[:-2])
        if not title:
            await update.message.reply_text("❌ Title cannot be empty.")
            return
        try:
            event = await google_calendar.create_event(title, date_str, time_str)
            link = event.get("htmlLink", "")
            link_suffix = f"\n[Open in Google Calendar]({link})" if link else ""
            await update.message.reply_text(
                f"✅ *Event created:* {title}\n"
                f"📅 {date_str} at {time_str} (1 hour){link_suffix}",
                parse_mode="Markdown",
            )
        except ValueError as exc:
            await update.message.reply_text(f"❌ {exc}")
        except Exception as exc:
            await update.message.reply_text(f"❌ Could not create event: {exc}")

    return {
        "calendar": calendar_command,
        "calendar-today": calendar_today_command,
        "schedule": schedule_command,
    }
