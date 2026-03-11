"""Tool context — single injection point for ToolRegistry dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...memory.knowledge import KnowledgeStore, KnowledgeExtractor
    from ...memory.facts import FactStore
    from ...memory.goals import GoalStore
    from ...memory.plans import PlanStore
    from ...memory.automations import AutomationStore
    from ...memory.background_jobs import BackgroundJobStore
    from ...memory.counters import CounterStore
    from ...memory.file_index import FileIndexer
    from ...analytics.analyzer import ConversationAnalyzer
    from ...ai.claude_client import ClaudeClient
    from ...ai.mistral_client import MistralClient
    from ...ai.moonshot_client import MoonshotClient
    from ...google.calendar import CalendarClient
    from ...google.gmail import GmailClient
    from ...google.contacts import ContactsClient
    from ...google.docs import DocsClient
    from ...startup_context import StartupContext
    from ...integrations.sms import SMSStore
    from ...integrations.wallet import WalletStore


class ToolContext:
    """All dependencies for tool executors. Single injection point for ToolRegistry.
    Supports lazy_google (US-lazy-service-init) for calendar, gmail, docs, contacts."""

    def __init__(
        self,
        logs_dir: str,
        knowledge_store: "KnowledgeStore | None" = None,
        knowledge_extractor: "KnowledgeExtractor | None" = None,
        claude_client: "ClaudeClient | None" = None,
        mistral_client: "MistralClient | None" = None,
        moonshot_client: "MoonshotClient | None" = None,
        ollama_base_url: str = "http://localhost:11434",
        model_complex: str = "claude-sonnet-4-6",
        calendar_client: "CalendarClient | None" = None,
        gmail_client: "GmailClient | None" = None,
        contacts_client: "ContactsClient | None" = None,
        docs_client: "DocsClient | None" = None,
        automation_store: "AutomationStore | None" = None,
        scheduler_ref: "StartupContext | None" = None,
        conversation_analyzer: "ConversationAnalyzer | None" = None,
        job_store: "BackgroundJobStore | None" = None,
        plan_store: "PlanStore | None" = None,
        file_indexer: "FileIndexer | None" = None,
        fact_store: "FactStore | None" = None,
        goal_store: "GoalStore | None" = None,
        counter_store: "CounterStore | None" = None,
        sms_store: "SMSStore | None" = None,
        wallet_store: "WalletStore | None" = None,
        lazy_google: Any = None,
    ) -> None:
        self.logs_dir = logs_dir
        self.knowledge_store = knowledge_store
        self.knowledge_extractor = knowledge_extractor
        self.claude_client = claude_client
        self.mistral_client = mistral_client
        self.moonshot_client = moonshot_client
        self.ollama_base_url = ollama_base_url
        self.model_complex = model_complex
        self._calendar_client = calendar_client
        self._gmail_client = gmail_client
        self._contacts_client = contacts_client
        self._docs_client = docs_client
        self._lazy_google = lazy_google
        self.automation_store = automation_store
        self.scheduler_ref = scheduler_ref
        self.conversation_analyzer = conversation_analyzer
        self.job_store = job_store
        self.plan_store = plan_store
        self.file_indexer = file_indexer
        self.fact_store = fact_store
        self.goal_store = goal_store
        self.counter_store = counter_store
        self.sms_store = sms_store
        self.wallet_store = wallet_store

    @property
    def calendar_client(self) -> "CalendarClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.calendar
        return self._calendar_client

    @property
    def gmail_client(self) -> "GmailClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.gmail
        return self._gmail_client

    @property
    def contacts_client(self) -> "ContactsClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.contacts
        return self._contacts_client

    @property
    def docs_client(self) -> "DocsClient | None":
        if self._lazy_google is not None:
            return self._lazy_google.docs
        return self._docs_client
