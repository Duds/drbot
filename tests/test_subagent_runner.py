"""
Tests for remy/agents/subagent_runner.py — SubagentRunner (board via subagent).

Covers the first milestone: board is executed by the runner, not by the handler
directly; runner delivers via BackgroundTaskRunner (US-subagents-next-plan).
"""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from remy.agents.background import BackgroundTaskRunner
from remy.agents.subagent_runner import SubagentRunner


async def _streaming_report(*chunks: str):
    """Async generator yielding chunks (simulates run_board_streaming)."""
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_start_board_raises_when_no_orchestrator():
    """SubagentRunner with no board_orchestrator raises on start_board."""
    runner = SubagentRunner(board_orchestrator=None)
    bot = MagicMock()
    bg = BackgroundTaskRunner(bot, chat_id=1)

    with pytest.raises(RuntimeError, match="board_orchestrator not configured"):
        runner.start_board(
            bg,
            topic="test",
            user_context="",
            user_id=42,
            session_key="sk",
        )


@pytest.mark.asyncio
async def test_board_via_subagent_delivers_concatenated_report():
    """start_board runs the board subagent and delivers via BackgroundTaskRunner."""
    chunk1 = "🟡 *Strategy* (1/5)…\n\n*📋 Strategy*\nAnalysis one.\n"
    chunk2 = "🟣 *Critic* (5/5)…\n\n*📋 Critic*\nVerdict.\n"

    orchestrator = MagicMock()

    # run_board_streaming is called and returns an async generator (not awaited first)
    def mock_streaming(*a, **kw):
        orchestrator.run_board_streaming_call = (a, kw)
        return _streaming_report(chunk1, chunk2)

    orchestrator.run_board_streaming = mock_streaming

    subagent_runner = SubagentRunner(board_orchestrator=orchestrator)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bg_runner = BackgroundTaskRunner(bot, chat_id=99)

    # Capture the task that start_board creates so we can await it
    created_tasks = []

    def capture_create_task(coro, *args, **kwargs):
        loop = asyncio.get_running_loop()
        t = loop.create_task(coro)
        created_tasks.append(t)
        return t

    with patch(
        "remy.agents.subagent_runner.asyncio.create_task",
        side_effect=capture_create_task,
    ):
        subagent_runner.start_board(
            bg_runner,
            topic="focus",
            user_context="",
            user_id=1,
            session_key="s1",
        )

    assert len(created_tasks) == 1
    await created_tasks[0]

    bot.send_message.assert_awaited()
    call_args = bot.send_message.call_args
    assert call_args[0][0] == 99
    body = call_args[0][1]
    # Body is MarkdownV2-escaped by BackgroundTaskRunner; check key content is present
    assert "Board of Directors: focus" in body
    assert "Strategy" in body and "Critic" in body
    assert "Analysis one" in body and "Verdict" in body
    assert orchestrator.run_board_streaming_call == (
        ("focus", ""),
        {"user_id": 1, "session_key": "s1"},
    )
