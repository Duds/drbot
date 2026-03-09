"""
Core command handlers.

Contains handlers for basic commands: start, help, cancel, status, setmychat, briefing.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .base import reject_unauthorized, _task_start_times
from ..session import SessionManager
from ...config import settings

if TYPE_CHECKING:
    from ...scheduler.proactive import ProactiveScheduler
    from ...ai.tools import ToolRegistry

logger = logging.getLogger(__name__)


def make_core_handlers(
    *,
    session_manager: SessionManager,
    tool_registry: "ToolRegistry | None" = None,
    proactive_scheduler: "ProactiveScheduler | None" = None,
    scheduler_ref: dict | None = None,
):
    """
    Factory that returns core command handlers.

    Returns a dict of command_name -> handler_function.
    """

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        await update.message.reply_text(
            "Remy online. I'm your conversational AI assistant.\n\n"
            "*Commands:*\n"
            "  /help  — show this overview\n"
            "  /cancel  — stop current task\n"
            "  /briefing  — morning briefing now\n"
            "  /status  — backend health\n"
            "  /setmychat  — set proactive message chat\n"
            "  /compact  — compress conversation\n"
            "  /delete_conversation  — clear history\n"
            "  /board <topic>  — Board of Directors analysis\n"
            "  /logs  — diagnostics summary\n"
            "  /stats  — usage stats\n"
            "  /costs  — API cost summary\n"
            "  /diagnostics  — full self-check\n\n"
            "For calendar, email, goals, files, web search, and more — just ask in natural language."
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_user is None:
            return
        await start_command(update, context)

    async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        user_id = update.effective_user.id
        session_manager.request_cancel(user_id)
        _task_start_times.pop(user_id, None)
        await update.message.reply_text("Stopping current task…")

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return

        if tool_registry is not None:
            status_text = await tool_registry.dispatch(
                "check_status", {}, update.effective_user.id
            )
            await update.message.reply_text(status_text)
        else:
            await update.message.reply_text(
                "Status check not available — tool registry not configured."
            )

    async def setmychat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        if update.effective_chat is None:
            return
        chat_id = str(update.effective_chat.id)
        path = settings.primary_chat_file
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        try:
            with open(path, "w") as f:
                f.write(chat_id)
            await update.message.reply_text(
                f"This chat is now set for proactive messages. (ID: {chat_id})"
            )
        except OSError as exc:
            await update.message.reply_text(f"Could not save: {exc}")

    async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger the morning briefing right now."""
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        _sched = (scheduler_ref or {}).get("proactive_scheduler") or proactive_scheduler
        if _sched is None:
            await update.message.reply_text("Proactive scheduler not running.")
            return
        await update.message.reply_text("Sending briefing…")
        await _sched.send_morning_briefing_now()

    return {
        "start": start_command,
        "help": help_command,
        "cancel": cancel_command,
        "status": status_command,
        "setmychat": setmychat_command,
        "briefing": briefing_command,
    }
