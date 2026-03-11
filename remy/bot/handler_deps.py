"""
Handler dependency containers — reduces make_handlers() parameter count.

Groups related dependencies so make_handlers() takes < 8 parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory.conversations import ConversationStore
    from ..memory.facts import FactStore
    from ..memory.goals import GoalStore
    from ..memory.injector import MemoryInjector
    from ..memory.knowledge import KnowledgeStore
    from ..memory.plans import PlanStore
    from ..memory.automations import AutomationStore
    from ..memory.background_jobs import BackgroundJobStore
    from ..memory.counters import CounterStore
    from ..agents.agent_task_lifecycle import AgentTaskStore
    from ..scheduler.proactive import ProactiveScheduler
    from ..google.calendar import CalendarClient
    from ..google.gmail import GmailClient
    from ..google.docs import DocsClient
    from ..google.contacts import ContactsClient
    from ..analytics.analyzer import ConversationAnalyzer


@dataclass(frozen=False)
class MemoryDeps:
    """Memory-related dependencies for handlers."""

    conv_store: "ConversationStore | None" = None
    knowledge_extractor: Any = None
    knowledge_store: "KnowledgeStore | None" = None
    fact_store: "FactStore | None" = None
    goal_store: "GoalStore | None" = None
    memory_injector: "MemoryInjector | None" = None
    plan_store: "PlanStore | None" = None


class GoogleDeps:
    """Google Workspace clients for handlers. Supports lazy init (US-lazy-service-init)."""

    def __init__(
        self,
        calendar: "CalendarClient | None" = None,
        gmail: "GmailClient | None" = None,
        docs: "DocsClient | None" = None,
        contacts: "ContactsClient | None" = None,
        lazy_google: Any = None,
    ) -> None:
        self._calendar = calendar
        self._gmail = gmail
        self._docs = docs
        self._contacts = contacts
        self._lazy_google = lazy_google

    @property
    def calendar(self) -> "CalendarClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.calendar
        return self._calendar

    @property
    def gmail(self) -> "GmailClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.gmail
        return self._gmail

    @property
    def docs(self) -> "DocsClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.docs
        return self._docs

    @property
    def contacts(self) -> "ContactsClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.contacts
        return self._contacts


@dataclass(frozen=False)
class SchedulerDeps:
    """Scheduler and automation dependencies for handlers."""

    proactive_scheduler: "ProactiveScheduler | None" = None
    scheduler_ref: Any = None
    automation_store: "AutomationStore | None" = None
    counter_store: "CounterStore | None" = None
    job_store: "BackgroundJobStore | None" = None
    agent_task_store: "AgentTaskStore | None" = None


@dataclass(frozen=False)
class CoreDeps:
    """Core handler dependencies (voice, analytics, diagnostics)."""

    voice_transcriber: Any = None
    conversation_analyzer: "ConversationAnalyzer | None" = None
    diagnostics_runner: Any = None
