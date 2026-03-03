"""
Google Docs handlers.

Contains handlers for Google Docs operations: reading and appending to documents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .base import reject_unauthorized, google_not_configured

if TYPE_CHECKING:
    from ...google.docs import DocsClient

logger = logging.getLogger(__name__)


def make_docs_handlers(
    *,
    google_docs: "DocsClient | None" = None,
    claude_client=None,
):
    """
    Factory that returns Google Docs handlers.

    Returns a dict of command_name -> handler_function.
    """

    async def gdoc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/gdoc <url-or-id> — read a Google Doc (large docs are summarised)."""
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        if google_docs is None:
            await update.message.reply_text(google_not_configured("Docs"))
            return
        if not context.args:
            await update.message.reply_text("Usage: /gdoc <google-doc-url-or-id>")
            return
        id_or_url = context.args[0]
        await update.message.reply_text("📄 Fetching document…")
        try:
            title, text = await google_docs.read_document(id_or_url)
        except Exception as exc:
            await update.message.reply_text(f"❌ Could not fetch doc: {exc}")
            return
        _SIZE_50KB = 50 * 1024
        if len(text.encode()) > _SIZE_50KB and claude_client is not None:
            await update.message.reply_text(
                f"📄 *{title}* is large. Summarising…", parse_mode="Markdown"
            )
            try:
                summary = await claude_client.complete(
                    messages=[
                        {
                            "role": "user",
                            "content": f"Summarise this document:\n\n{text[:20000]}",
                        }
                    ],
                    system="You are a document summarisation assistant. Be concise and factual.",
                    max_tokens=512,
                )
                await update.message.reply_text(
                    f"📄 *Summary of {title}:*\n\n{summary}", parse_mode="Markdown"
                )
            except Exception as exc:
                await update.message.reply_text(f"❌ Could not summarise: {exc}")
            return
        if len(text) > 8000:
            text = text[:8000] + "\n…[truncated]"
        await update.message.reply_text(
            f"📄 *{title}*\n\n```\n{text}\n```",
            parse_mode="Markdown",
        )

    async def gdoc_append_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/gdoc-append <url-or-id> <text> — append text to a Google Doc."""
        if update.message is None or update.effective_user is None:
            return
        if await reject_unauthorized(update):
            return
        if google_docs is None:
            await update.message.reply_text(google_not_configured("Docs"))
            return
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /gdoc-append <google-doc-url-or-id> <text to append>"
            )
            return
        id_or_url = context.args[0]
        text_to_append = " ".join(context.args[1:])
        try:
            await google_docs.append_text(id_or_url, text_to_append)
            await update.message.reply_text("✅ Text appended to document.")
        except Exception as exc:
            await update.message.reply_text(f"❌ Could not append to doc: {exc}")

    return {
        "gdoc": gdoc_command,
        "gdoc-append": gdoc_append_command,
    }
