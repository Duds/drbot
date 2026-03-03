"""
Tests for relay client (direct DB writes to relay.db). US-claude-desktop-relay.
"""

import json
import tempfile
from pathlib import Path

import pytest

from remy.relay.client import (
    get_messages_for_remy,
    get_tasks_for_remy,
    post_message_to_cowork,
    post_note,
    update_task,
)


@pytest.fixture
def temp_data_dir():
    """Temporary directory for relay.db."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.mark.asyncio
async def test_post_message_to_cowork_creates_message(temp_data_dir):
    """Post message writes to relay.db."""
    result = await post_message_to_cowork("Hello cowork", data_dir=temp_data_dir)
    assert result is not None

    import aiosqlite

    path = Path(temp_data_dir) / "relay.db"
    assert path.exists()
    async with aiosqlite.connect(str(path)) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT id, from_agent, to_agent, content FROM messages"
        ) as cur:
            rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["from_agent"] == "remy"
    assert rows[0]["to_agent"] == "cowork"
    assert rows[0]["content"] == "Hello cowork"


@pytest.mark.asyncio
async def test_post_message_empty_returns_false(temp_data_dir):
    """Empty content returns None."""
    assert await post_message_to_cowork("", data_dir=temp_data_dir) is None
    assert await post_message_to_cowork("   ", data_dir=temp_data_dir) is None


@pytest.mark.asyncio
async def test_post_note_creates_note(temp_data_dir):
    """Post note writes to shared_notes."""
    result = await post_note(
        "Gmail audit complete", tags=["gmail", "audit"], data_dir=temp_data_dir
    )
    assert result is not None

    import aiosqlite

    path = Path(temp_data_dir) / "relay.db"
    async with aiosqlite.connect(str(path)) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT id, from_agent, content, tags FROM shared_notes"
        ) as cur:
            rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["from_agent"] == "remy"
    assert rows[0]["content"] == "Gmail audit complete"
    assert json.loads(rows[0]["tags"]) == ["gmail", "audit"]


@pytest.mark.asyncio
async def test_get_messages_returns_unread_and_count(temp_data_dir):
    """get_messages_for_remy returns (messages, unread_count); mark_read marks as read."""
    import aiosqlite
    from datetime import datetime, timezone

    path = Path(temp_data_dir) / "relay.db"
    from remy.relay.client import _ensure_db

    await _ensure_db(path)

    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(str(path)) as conn:
        await conn.execute(
            "INSERT INTO messages (id, from_agent, to_agent, content, thread_id, read, created_at) VALUES (?,?,?,?,?,0,?)",
            ("a1", "cowork", "remy", "First", "t1", now),
        )
        await conn.execute(
            "INSERT INTO messages (id, from_agent, to_agent, content, thread_id, read, created_at) VALUES (?,?,?,?,?,0,?)",
            ("a2", "cowork", "remy", "Second", "t1", now),
        )
        await conn.commit()

    messages, unread_count = await get_messages_for_remy(
        data_dir=temp_data_dir, mark_read=False
    )
    assert len(messages) == 2
    assert unread_count == 2

    messages2, unread_after = await get_messages_for_remy(
        data_dir=temp_data_dir, mark_read=True
    )
    assert len(messages2) == 2
    assert unread_after == 0

    messages3, unread3 = await get_messages_for_remy(
        data_dir=temp_data_dir, unread_only=True
    )
    assert len(messages3) == 0
    assert unread3 == 0


@pytest.mark.asyncio
async def test_get_tasks_and_update_task(temp_data_dir):
    """get_tasks_for_remy returns (tasks, pending_count); update_task updates status."""
    import aiosqlite
    from datetime import datetime, timezone

    path = Path(temp_data_dir) / "relay.db"
    from remy.relay.client import _ensure_db

    await _ensure_db(path)

    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(str(path)) as conn:
        await conn.execute(
            "INSERT INTO tasks (id, from_agent, to_agent, task_type, description, params, status, result, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "tid1",
                "cowork",
                "remy",
                "gmail_label",
                "Label Radford emails",
                "{}",
                "pending",
                None,
                None,
                now,
                now,
            ),
        )
        await conn.commit()

    tasks, pending_count = await get_tasks_for_remy(
        data_dir=temp_data_dir, status="pending"
    )
    assert len(tasks) == 1
    assert pending_count == 1
    assert tasks[0]["id"] == "tid1"
    assert tasks[0]["status"] == "pending"

    result = await update_task("tid1", "in_progress", data_dir=temp_data_dir)
    assert result is not None
    assert result.get("status") == "in_progress"

    result2 = await update_task(
        "tid1", "done", result="Labelled 32 emails.", data_dir=temp_data_dir
    )
    assert result2 is not None

    tasks_done, pending = await get_tasks_for_remy(
        data_dir=temp_data_dir, status="done"
    )
    assert len(tasks_done) == 1
    assert tasks_done[0]["result"] == "Labelled 32 emails."
    assert pending == 0


@pytest.mark.asyncio
async def test_relay_round_trip(temp_data_dir):
    """Integration: cowork sends message -> Remy reads -> Remy replies -> cowork has reply."""
    import aiosqlite
    from datetime import datetime, timezone

    path = Path(temp_data_dir) / "relay.db"
    from remy.relay.client import _ensure_db

    await _ensure_db(path)

    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(str(path)) as conn:
        await conn.execute(
            "INSERT INTO messages (id, from_agent, to_agent, content, thread_id, read, created_at) VALUES (?,?,?,?,?,0,?)",
            ("m1", "cowork", "remy", "Please label Radford emails.", "m1", now),
        )
        await conn.commit()

    messages, unread = await get_messages_for_remy(
        data_dir=temp_data_dir, mark_read=True
    )
    assert len(messages) == 1
    assert messages[0]["content"] == "Please label Radford emails."
    assert unread == 0

    result = await post_message_to_cowork(
        "Done — labelled 32 emails as 4-Personal.",
        data_dir=temp_data_dir,
    )
    assert result is not None

    async with aiosqlite.connect(str(path)) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT from_agent, to_agent, content FROM messages WHERE to_agent = ?",
            ("cowork",),
        ) as cur:
            rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["from_agent"] == "remy"
    assert rows[0]["to_agent"] == "cowork"
    assert "32 emails" in rows[0]["content"]
