"""Shared fixtures for remy tests."""

from __future__ import annotations

import pytest


def minimal_make_handlers_kwargs(**overrides):
    """Minimal kwargs for make_handlers() — use for tests that need a minimal setup."""
    from remy.bot.handler_deps import GoogleDeps, MemoryDeps

    base = {
        "session_manager": None,
        "claude_client": None,
        "db": None,
        "tool_registry": None,
        "memory_deps": MemoryDeps(conv_store=None),
        "google_deps": GoogleDeps(),
        "scheduler_deps": None,
        "core_deps": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for tests."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch, tmp_path):
    """Prevent tests from reading real .env or touching real data."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS_RAW", "12345")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AZURE_ENVIRONMENT", "false")
