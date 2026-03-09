"""
Integration test: spawn a sub-agent that is required to use tools.

Proves the full path:
  1. Main agent hits max_iterations → HandOffToSubAgent(topic) is yielded.
  2. We run a "sub-agent" coroutine (simulating what the handler does).
  3. The sub-agent uses the tool registry (e.g. get_current_time) and returns a result.
  4. We assert hand-off was received, sub-agent ran, tool was dispatched, result is valid.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from remy.ai.claude_client import ClaudeClient, HandOffToSubAgent
from remy.ai.tools import ToolRegistry


USER_ID = 99


def _make_stream_event(event_type: str, **kwargs):
    evt = MagicMock()
    evt.__class__.__name__ = event_type
    for k, v in kwargs.items():
        setattr(evt, k, v)
    return evt


def _make_tool_use_stream(
    tool_name: str = "get_current_time", tool_id: str = "toolu_1"
):
    """Return a mock stream that yields one tool_use and final message with stop_reason=tool_use."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = tool_name
    tool_block.input = {}

    final_msg = MagicMock()
    final_msg.stop_reason = "tool_use"
    final_msg.content = [tool_block]
    final_msg.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )

    async def fake_iter():
        yield _make_stream_event("RawContentBlockStartEvent", content_block=tool_block)

    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)
    mock_stream.__aiter__ = lambda self: fake_iter().__aiter__()
    mock_stream.get_final_message = AsyncMock(return_value=final_msg)
    return mock_stream


@pytest.mark.asyncio
async def test_hand_off_then_subagent_uses_tools(tmp_path):
    """
    When main agent hits max_iterations we get HandOffToSubAgent; we then run
    a sub-agent coroutine that dispatches a tool and returns its result.
    """
    # 1. Mock stream to hit max_iterations (e.g. 2): two tool_use iterations, then we exit and yield hand-off
    stream1 = _make_tool_use_stream("get_current_time", "toolu_1")
    stream2 = _make_tool_use_stream("get_goals", "toolu_2")  # second iteration

    client = ClaudeClient.__new__(ClaudeClient)
    client._client = MagicMock()
    client._client.messages.stream = MagicMock(side_effect=[stream1, stream2])

    registry = ToolRegistry(logs_dir=str(tmp_path))
    dispatch_calls: list[tuple[str, dict]] = []

    async def record_dispatch(name, inp, uid, chat_id=None, message_id=None):
        dispatch_calls.append((name, inp))
        if name == "get_current_time":
            from remy.ai.tools.time import exec_get_current_time

            return exec_get_current_time(registry)
        return "No goals configured."

    registry.dispatch = AsyncMock(side_effect=record_dispatch)

    with patch("remy.ai.claude_client.settings") as mock_settings:
        mock_settings.anthropic_max_tool_iterations = 2
        mock_settings.anthropic_max_tokens = 4096

        events = []
        async for event in client.stream_with_tools(
            messages=[
                {"role": "user", "content": "What time is it? Then list my goals."}
            ],
            tool_registry=registry,
            user_id=USER_ID,
        ):
            events.append(event)

    hand_offs = [e for e in events if isinstance(e, HandOffToSubAgent)]
    assert len(hand_offs) == 1, "Expected one HandOffToSubAgent after max_iterations"
    topic = hand_offs[0].topic
    assert topic, "Hand-off topic must be non-empty"

    # 2. Simulate handler: run a sub-agent that uses tools (same registry)
    async def run_subagent(reg: ToolRegistry, hand_off_topic: str, user_id: int) -> str:
        """Sub-agent that must use a tool to answer (e.g. get current time for context)."""
        time_result = await reg.dispatch("get_current_time", {}, user_id, None, None)
        return f"Sub-agent received topic: {hand_off_topic[:50]}. Current time: {time_result[:80]}."

    subagent_result = await run_subagent(registry, topic, USER_ID)

    # 3. Assert sub-agent ran and used tools
    assert "Sub-agent received topic" in subagent_result
    assert "Current time" in subagent_result
    assert "Australia" in subagent_result or "Canberra" in subagent_result, (
        "get_current_time should return AU time"
    )
    # Main stream already dispatched get_current_time and get_goals (2 iterations); sub-agent dispatched get_current_time again
    assert any(c[0] == "get_current_time" for c in dispatch_calls)
    assert len(dispatch_calls) >= 1


@pytest.mark.asyncio
async def test_subagent_tool_sequence_recorded(tmp_path):
    """
    Sub-agent runs multiple tool calls in sequence; we record and assert the order.
    """
    registry = ToolRegistry(logs_dir=str(tmp_path))
    sequence: list[str] = []

    async def record_dispatch(name, inp, uid, chat_id=None, message_id=None):
        sequence.append(name)
        if name == "get_current_time":
            from remy.ai.tools.time import exec_get_current_time

            return exec_get_current_time(registry)
        if name == "get_goals":
            return "Goal list (empty for test)."
        return "ok"

    registry.dispatch = AsyncMock(side_effect=record_dispatch)

    async def subagent_with_two_tools(reg: ToolRegistry, user_id: int) -> str:
        t = await reg.dispatch("get_current_time", {}, user_id, None, None)
        g = await reg.dispatch("get_goals", {}, user_id, None, None)
        return f"Time: {t[:40]}... Goals: {g[:40]}."

    result = await subagent_with_two_tools(registry, USER_ID)

    assert sequence == ["get_current_time", "get_goals"]
    assert "Time:" in result
    assert "Goals:" in result
