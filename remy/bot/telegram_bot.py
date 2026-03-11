"""
Telegram bot application builder and runner.
Registers all handlers and starts polling or webhook depending on environment.

Connection resilience: Configures generous timeouts to handle transient
Telegram API disconnections gracefully (Bug 6 mitigation).
"""

import logging
import os

import telegram.error
from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    MessageReactionHandler,
    filters,
)

from ..config import settings

logger = logging.getLogger(__name__)

# Removed commands: reply with redirect to natural language (US-command-surface-reduction)
_REDIRECT_MESSAGES: dict[str, str] = {
    "calendar": "Use natural language — just ask me about your calendar directly.",
    "goals": "Just ask me in natural language, e.g. “What are my goals?” or “Add a goal”.",
    "plans": "Just ask me about plans in natural language.",
    "gmail_unread": "Ask me in natural language, e.g. “What’s in my inbox?”.",
    "contacts": "Ask me about contacts in natural language.",
    "search": "Just ask me what you want to find.",
    "bookmarks": "Ask me about bookmarks in natural language.",
    "research": "Ask me to research a topic in natural language.",
    "reminders": "Ask me about reminders or set one in natural language.",
    "read": "Ask me to read a file by describing the path or file.",
    "write": "Ask me to write to a file in natural language.",
    "ls": "Ask me to list files or directories in natural language.",
    "find": "Ask me to find files or content in natural language.",
    "routing": "Routing stats are available via /diagnostics. For custom analysis, ask in natural language.",
}


def _make_redirect_handler(cmd: str):
    """Return a handler that replies with the redirect message for a removed command."""

    async def _redirect(update, context):
        if update.message is None:
            return
        msg = _REDIRECT_MESSAGES.get(
            cmd, "That command is no longer available. Just ask me in natural language."
        )
        await update.message.reply_text(msg)

    return _redirect


def _register_redirect_handlers(application) -> None:
    """Register CommandHandlers for removed commands so they return a redirect message."""
    for cmd in _REDIRECT_MESSAGES:
        # Telegram allows only a-z, 0-9, underscore; use cmd as slash name (e.g. /gmail_unread)
        application.add_handler(CommandHandler(cmd, _make_redirect_handler(cmd)))


# US-command-surface-reduction: ≤15 commands in BotFather menu
PHASE3_BOT_COMMANDS = [
    BotCommand("start", "Show overview"),
    BotCommand("help", "Show overview"),
    BotCommand("cancel", "Stop current task"),
    BotCommand("briefing", "Morning briefing now"),
    BotCommand("status", "Backend health"),
    BotCommand("setmychat", "Set proactive message chat"),
    BotCommand("compact", "Compress conversation"),
    BotCommand("delete_conversation", "Clear history"),
    BotCommand("board", "Board of Directors analysis"),
    BotCommand("diagnostics", "Full self-check"),
    BotCommand("logs", "Diagnostics summary"),
    BotCommand("stats", "Usage stats"),
    BotCommand("costs", "API cost summary"),
]


async def _set_phase3_commands(application: Application) -> None:
    """Post-init: set bot command list so Telegram menu shows only Phase 3 commands."""
    try:
        await application.bot.set_my_commands(PHASE3_BOT_COMMANDS)
    except Exception as e:
        logger.warning("set_my_commands failed: %s", e)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all error handler registered with PTB Application.

    Transient errors (network, timeout, forbidden) are logged at WARNING.
    Unexpected errors are logged at ERROR with update context and trigger
    a Telegram alert to the first allowed user.
    """
    err = context.error

    # Record error in Prometheus metrics if available
    try:
        from ..analytics.metrics import record_error

        if isinstance(err, telegram.error.NetworkError):
            record_error("telegram_network")
        elif isinstance(err, telegram.error.TimedOut):
            record_error("telegram_timeout")
        else:
            record_error("telegram_other")
    except ImportError:
        pass

    if isinstance(
        err,
        (
            telegram.error.NetworkError,
            telegram.error.TimedOut,
            telegram.error.Forbidden,
        ),
    ):
        logger.warning("Telegram transient error: %s", err)
        return

    user_id = None
    update_type = type(update).__name__ if update else "unknown"
    if hasattr(update, "effective_user") and update.effective_user:
        user_id = update.effective_user.id
    logger.error(
        "Unhandled Telegram exception (update_type=%s, user=%s): %s",
        update_type,
        user_id,
        err,
        exc_info=context.error,
    )
    if settings.telegram_allowed_users:
        try:
            await context.bot.send_message(
                chat_id=settings.telegram_allowed_users[0],
                text=f"\u26a0\ufe0f *Remy error:* `{type(err).__name__}: {err}`",
                parse_mode="Markdown",
            )
        except Exception as notify_err:
            logger.debug("Failed to send error notification to admin: %s", notify_err)


class TelegramBot:
    def __init__(self, handlers: dict) -> None:
        # Build application with resilient timeout configuration
        timeout = settings.telegram_timeout
        self.application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .http_version("1.1")
            .connect_timeout(timeout)
            .read_timeout(timeout)
            .write_timeout(timeout)
            .pool_timeout(timeout)
            .get_updates_connect_timeout(timeout)
            .get_updates_read_timeout(timeout)
            .get_updates_write_timeout(timeout)
            .get_updates_pool_timeout(timeout)
            .post_init(_set_phase3_commands)
            .build()
        )
        self._register_handlers(handlers)

    def _register_handlers(self, handlers: dict) -> None:
        app = self.application
        # Phase 3: Collapsed command surface — core + domain only (≤15)
        app.add_handler(CommandHandler("start", handlers["start"]))
        app.add_handler(CommandHandler("help", handlers["help"]))
        app.add_handler(CommandHandler("cancel", handlers["cancel"]))
        app.add_handler(CommandHandler("status", handlers["status"]))
        app.add_handler(CommandHandler("compact", handlers["compact"]))
        app.add_handler(CommandHandler("setmychat", handlers["setmychat"]))
        app.add_handler(CommandHandler("briefing", handlers["briefing"]))
        app.add_handler(
            CommandHandler("delete_conversation", handlers["delete_conversation"])
        )
        app.add_handler(CommandHandler("board", handlers["board"]))
        app.add_handler(CommandHandler("logs", handlers["logs"]))
        app.add_handler(CommandHandler("stats", handlers["stats"]))
        app.add_handler(CommandHandler("costs", handlers["costs"]))
        app.add_handler(CommandHandler("diagnostics", handlers["diagnostics"]))
        # Redirect handlers for removed commands (US-command-surface-reduction)
        _register_redirect_handlers(app)
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["message"])
        )
        app.add_handler(MessageHandler(filters.VOICE, handlers["voice"]))
        app.add_handler(MessageHandler(filters.PHOTO, handlers["photo"]))
        app.add_handler(MessageHandler(filters.Document.ALL, handlers["document"]))
        app.add_handler(MessageReactionHandler(handlers["reaction"]))
        if handlers.get("callback"):
            app.add_handler(CallbackQueryHandler(handlers["callback"]))
        app.add_error_handler(_error_handler)

    def run(self) -> None:
        """Start the bot (blocking). Use run_polling locally, webhook in Azure."""
        if settings.azure_environment:
            webhook_url = os.environ.get("WEBHOOK_URL")
            if webhook_url:
                logger.info("Starting bot with webhook: %s", webhook_url)
                self.application.run_webhook(
                    listen="0.0.0.0",
                    port=int(os.environ.get("PORT", 8443)),
                    webhook_url=webhook_url,
                )
                return
        logger.info("Starting bot with polling")
        from telegram import Update

        self.application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
