"""Tool context — single injection point for ToolRegistry dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class ToolContext:
    """All dependencies for tool executors. Single injection point for ToolRegistry."""

    logs_dir: str
    knowledge_store: "KnowledgeStore | None" = None
    knowledge_extractor: "KnowledgeExtractor | None" = None
    claude_client: "ClaudeClient | None" = None
    mistral_client: "MistralClient | None" = None
    moonshot_client: "MoonshotClient | None" = None
    ollama_base_url: str = "http://localhost:11434"
    model_complex: str = "claude-sonnet-4-6"
    calendar_client: "CalendarClient | None" = None
    gmail_client: "GmailClient | None" = None
    contacts_client: "ContactsClient | None" = None
    docs_client: "DocsClient | None" = None
    automation_store: "AutomationStore | None" = None
    scheduler_ref: "StartupContext | None" = None
    conversation_analyzer: "ConversationAnalyzer | None" = None
    job_store: "BackgroundJobStore | None" = None
    plan_store: "PlanStore | None" = None
    file_indexer: "FileIndexer | None" = None
    fact_store: "FactStore | None" = None
    goal_store: "GoalStore | None" = None
    counter_store: "CounterStore | None" = None
    sms_store: "SMSStore | None" = None
    wallet_store: "WalletStore | None" = None
