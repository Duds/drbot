"""
Base class for briefing generators.

Provides common utilities and dependency injection pattern for all briefing types.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...config import settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ...memory.goals import GoalStore
    from ...memory.knowledge import KnowledgeStore
    from ...memory.plans import PlanStore
    from ...memory.facts import FactStore
    from ...memory.file_index import FileIndexer
    from ...google.calendar import CalendarClient
    from ...google.contacts import ContactsClient
    from ...google.gmail import GmailClient
    from ...ai.claude_client import ClaudeClient
    from ...analytics.analyzer import ConversationAnalyzer


class BriefingGenerator(ABC):
    """
    Abstract base class for briefing content generators.

    Subclasses implement `generate()` to produce briefing content.
    Dependencies are injected via constructor to enable testing and flexibility.
    """

    def __init__(
        self,
        user_id: int,
        goal_store: "GoalStore | None" = None,
        knowledge_store: "KnowledgeStore | None" = None,
        plan_store: "PlanStore | None" = None,
        fact_store: "FactStore | None" = None,
        calendar: "CalendarClient | None" = None,
        contacts: "ContactsClient | None" = None,
        gmail: "GmailClient | None" = None,
        file_indexer: "FileIndexer | None" = None,
        claude: "ClaudeClient | None" = None,
        conversation_analyzer: "ConversationAnalyzer | None" = None,
    ) -> None:
        self._user_id = user_id
        self._goal_store = goal_store
        self._knowledge_store = knowledge_store
        self._plan_store = plan_store
        self._fact_store = fact_store
        self._calendar = calendar
        self._contacts = contacts
        self._gmail = gmail
        self._file_indexer = file_indexer
        self._claude = claude
        self._conversation_analyzer = conversation_analyzer

    @abstractmethod
    async def generate(self) -> str:
        """Generate the briefing content. Returns empty string if nothing to report."""
        pass

    async def _get_active_goals(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch active goals for the user."""
        if self._knowledge_store is not None:
            return await self._knowledge_store.get_goals_active(
                self._user_id, limit=limit
            )
        if not self._goal_store:
            return []
        return await self._goal_store.get_active(self._user_id, limit=limit)

    async def _get_stale_goals(self, days: int = 3) -> list[dict[str, Any]]:
        """Fetch goals not updated within N days."""
        goals = await self._get_active_goals(limit=10)
        if not goals:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stale = []
        for g in goals:
            ts_str = g.get("updated_at") or g.get("created_at") or ""
            if not ts_str:
                stale.append(g)  # No timestamp: treat as stale
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    stale.append(g)
            except (ValueError, TypeError):
                stale.append(g)
        return stale

    def _format_date_header(self) -> str:
        """Return formatted date string for briefing headers."""
        tz_name = getattr(settings, "scheduler_timezone", "UTC")
        tz: ZoneInfo | timezone = timezone.utc
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, ZoneInfoNotFoundError):
            logger.warning(
                "_format_date_header: unknown timezone %r, falling back to UTC", tz_name
            )
        return datetime.now(tz).strftime("%A, %d %B")

    def _format_date_australian(self, d: datetime | None = None) -> str:
        """Return Australian-style date: DD/MM/YYYY or 'dd MMM' for display.
        Uses scheduler_timezone. If d is None, uses now."""
        tz_name = getattr(settings, "scheduler_timezone", "UTC")
        tz: ZoneInfo | timezone = timezone.utc
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, ZoneInfoNotFoundError):
            pass
        dt = (d or datetime.now(tz)).astimezone(tz)
        return dt.strftime("%d/%m/%Y")

    def _format_date_australian_short(self, d: datetime | None = None) -> str:
        """Return short Australian date: '03 Mar' style."""
        tz_name = getattr(settings, "scheduler_timezone", "UTC")
        tz: ZoneInfo | timezone = timezone.utc
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, ZoneInfoNotFoundError):
            pass
        dt = (d or datetime.now(tz)).astimezone(tz)
        return dt.strftime("%d %b")
