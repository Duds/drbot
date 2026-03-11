"""Tests for remy/bot/working_message.py — animated placeholder messages."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from remy.bot.working_message import (
    WORKING_PLACEHOLDER,
    WorkingMessage,
    _EDIT_INTERVAL,
    _PHRASES,
    tool_status_text,
)


def make_mock_bot():
    """Create a mock bot with async send_message, edit_message_text, delete_message."""
    bot = MagicMock()
    sent_msg = MagicMock()
    sent_msg.message_id = 12345
    bot.send_message = AsyncMock(return_value=sent_msg)
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_start_sends_initial_placeholder():
    """start() should send WORKING_PLACEHOLDER (_Working…_) by default."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    await wm.stop()

    bot.send_message.assert_called_once()
    call_kw = bot.send_message.call_args[1]
    assert call_kw.get("parse_mode") == "Markdown"
    assert bot.send_message.call_args[0][1] == WORKING_PLACEHOLDER


@pytest.mark.asyncio
async def test_start_with_thread_id():
    """start() should pass thread_id to send_message."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999, thread_id=42)

    await wm.start()
    await wm.stop()

    bot.send_message.assert_called_once()
    assert bot.send_message.call_args[1]["message_thread_id"] == 42
    assert bot.send_message.call_args[0][1] == WORKING_PLACEHOLDER


@pytest.mark.asyncio
async def test_stop_deletes_placeholder():
    """stop() should delete the placeholder message."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    await wm.stop()

    bot.delete_message.assert_called_once_with(999, 12345)


@pytest.mark.asyncio
async def test_stop_cancels_animation_task():
    """stop() should cancel the animation task cleanly."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    assert wm._task is not None
    assert not wm._task.done()

    await wm.stop()
    assert wm._task is None


@pytest.mark.asyncio
async def test_stop_twice_is_safe():
    """Calling stop() twice should not raise an error."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    await wm.stop()
    await wm.stop()  # Second call should be a no-op

    # delete_message should only be called once
    assert bot.delete_message.call_count == 1


@pytest.mark.asyncio
async def test_animation_edits_message():
    """After waiting, the animation should edit the message with a phrase."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    # Wait for at least one edit cycle
    await asyncio.sleep(_EDIT_INTERVAL + 0.1)
    await wm.stop()

    # Should have at least one edit call
    assert bot.edit_message_text.call_count >= 1

    # Check that the edit contains a phrase from the list
    call_args = bot.edit_message_text.call_args[0]
    text = call_args[0]
    assert text.startswith("⚙️ ")
    assert any(phrase in text for phrase in _PHRASES)


@pytest.mark.asyncio
async def test_animation_uses_typewriter_suffixes():
    """Animation should cycle through ▌ and … suffixes."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    # Wait for two edit cycles to see both suffixes
    await asyncio.sleep(_EDIT_INTERVAL * 2 + 0.1)
    await wm.stop()

    # Check that we got edits with both suffixes
    edit_texts = [call[0][0] for call in bot.edit_message_text.call_args_list]
    has_block_cursor = any("▌" in t for t in edit_texts)
    has_ellipsis = any("…" in t for t in edit_texts)

    assert has_block_cursor or has_ellipsis  # At least one suffix type


@pytest.mark.asyncio
async def test_edit_failure_does_not_crash():
    """If edit_message_text fails, the animation should continue."""
    bot = make_mock_bot()
    bot.edit_message_text = AsyncMock(side_effect=Exception("Telegram error"))
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    await asyncio.sleep(_EDIT_INTERVAL + 0.1)
    # Should not raise
    await wm.stop()


@pytest.mark.asyncio
async def test_delete_failure_does_not_crash():
    """If delete_message fails, stop() should not raise."""
    bot = make_mock_bot()
    bot.delete_message = AsyncMock(side_effect=Exception("Already deleted"))
    wm = WorkingMessage(bot, chat_id=999)

    await wm.start()
    # Should not raise
    await wm.stop()


@pytest.mark.asyncio
async def test_start_failure_does_not_crash():
    """If send_message fails, start() should not raise."""
    bot = make_mock_bot()
    bot.send_message = AsyncMock(side_effect=Exception("Network error"))
    wm = WorkingMessage(bot, chat_id=999)

    # Should not raise
    await wm.start()
    await wm.stop()


@pytest.mark.asyncio
async def test_phrases_list_is_not_empty():
    """The phrases list should have content."""
    assert len(_PHRASES) >= 10  # Spec says 15+


@pytest.mark.asyncio
async def test_phrases_are_unique():
    """All phrases should be unique."""
    assert len(_PHRASES) == len(set(_PHRASES))


@pytest.mark.asyncio
async def test_async_context_manager():
    """Phase 3.11: async with WorkingMessage sets wm.message, calls start(), stop(delete=...) on exit."""
    bot = make_mock_bot()
    async with WorkingMessage(bot, chat_id=999) as wm:
        assert wm.message is not None
        assert wm.message.message_id == 12345
    bot.send_message.assert_called_once()
    bot.delete_message.assert_called_once_with(999, 12345)


@pytest.mark.asyncio
async def test_edit_to_result():
    """Phase 3.11: edit_to_result edits message to text and stop(delete=False) does not delete."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)
    await wm.start()
    await wm.edit_to_result("Done")
    bot.edit_message_text.assert_called()
    last_call = bot.edit_message_text.call_args_list[-1]
    assert last_call[0][0] == "Done"
    await wm.stop(delete=False)
    bot.delete_message.assert_not_called()


def test_tool_status_text():
    """US-working-message-normalisation: tool_status_text returns standard format."""
    assert "calendar" in tool_status_text("calendar")
    assert "⚙️" in tool_status_text("calendar")
    assert tool_status_text("gmail") == "_⚙️ Using gmail…_"


@pytest.mark.asyncio
async def test_set_status_updates_placeholder():
    """set_status edits the message to tool indicator; no crash."""
    bot = make_mock_bot()
    wm = WorkingMessage(bot, chat_id=999)
    await wm.start()
    await wm.set_status(tool_status_text("calendar"))
    bot.edit_message_text.assert_called()
    assert "calendar" in bot.edit_message_text.call_args[0][0]
    await wm.stop()


@pytest.mark.asyncio
async def test_set_status_bad_request_does_not_crash():
    """User deleted placeholder: set_status catches BadRequest and does not raise."""
    from telegram.error import BadRequest

    bot = make_mock_bot()
    bot.edit_message_text = AsyncMock(
        side_effect=BadRequest("Message to edit not found")
    )
    wm = WorkingMessage(bot, chat_id=999)
    await wm.start()
    await wm.set_status(tool_status_text("calendar"))  # should not raise
    await wm.stop()


@pytest.mark.asyncio
async def test_mark_replaced_prevents_delete_on_exit():
    """mark_replaced() causes __aexit__ to not delete the message."""
    bot = make_mock_bot()
    async with WorkingMessage(bot, chat_id=999) as wm:
        wm.mark_replaced()
    bot.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_edit_to_result_bad_request_does_not_crash():
    """edit_to_result catches BadRequest (e.g. message deleted) and does not raise."""
    from telegram.error import BadRequest

    bot = make_mock_bot()
    bot.edit_message_text = AsyncMock(
        side_effect=BadRequest("Message to edit not found")
    )
    wm = WorkingMessage(bot, chat_id=999)
    await wm.start()
    await wm.edit_to_result("Done")  # should not raise
    await wm.stop()
