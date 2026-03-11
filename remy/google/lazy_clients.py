"""
Lazy Google Workspace clients (US-lazy-service-init).

Creates Calendar, Gmail, Docs, and Contacts clients on first use so startup
stays under ~3s. Thread-safe: use asyncio.Lock for first-use in async context
if needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .calendar import CalendarClient
    from .contacts import ContactsClient
    from .docs import DocsClient
    from .gmail import GmailClient


class LazyGoogleClients:
    """Holds Google Workspace client factories; creates each client on first property access."""

    def __init__(
        self,
        token_file: str,
        timezone: str = "Australia/Sydney",
    ) -> None:
        self._token_file = token_file
        self._timezone = timezone
        self._calendar: "CalendarClient | None" = None
        self._gmail: "GmailClient | None" = None
        self._docs: "DocsClient | None" = None
        self._contacts: "ContactsClient | None" = None

    @property
    def calendar(self) -> "CalendarClient | None":
        if self._calendar is None:
            try:
                from .calendar import CalendarClient

                self._calendar = CalendarClient(
                    self._token_file, timezone=self._timezone
                )
                logger.info("Google Calendar client initialised (lazy)")
            except Exception as e:
                logger.warning("Google Calendar lazy init failed: %s", e)
        return self._calendar

    @property
    def gmail(self) -> "GmailClient | None":
        if self._gmail is None:
            try:
                from .gmail import GmailClient

                self._gmail = GmailClient(self._token_file)
                logger.info("Google Gmail client initialised (lazy)")
            except Exception as e:
                logger.warning("Google Gmail lazy init failed: %s", e)
        return self._gmail

    @property
    def docs(self) -> "DocsClient | None":
        if self._docs is None:
            try:
                from .docs import DocsClient

                self._docs = DocsClient(self._token_file)
                logger.info("Google Docs client initialised (lazy)")
            except Exception as e:
                logger.warning("Google Docs lazy init failed: %s", e)
        return self._docs

    @property
    def contacts(self) -> "ContactsClient | None":
        if self._contacts is None:
            try:
                from .contacts import ContactsClient

                self._contacts = ContactsClient(self._token_file)
                logger.info("Google Contacts client initialised (lazy)")
            except Exception as e:
                logger.warning("Google Contacts lazy init failed: %s", e)
        return self._contacts
