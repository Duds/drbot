"""
Tests for reverse file reading in conversations.py.
"""

import asyncio
import os
import tempfile
import pytest

from remy.memory.conversations import ConversationStore
from remy.models import ConversationTurn


class TestReverseFileReading:
    """Test efficient reverse file reading for conversation history."""

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def conv_store(self, temp_sessions_dir):
        """Create a ConversationStore with temp directory."""
        return ConversationStore(temp_sessions_dir)

    @pytest.mark.asyncio
    async def test_get_recent_turns_empty_file(self, conv_store):
        """Empty session returns empty list."""
        turns = await conv_store.get_recent_turns(123, "user_123_2024-01-01", limit=10)
        assert turns == []

    @pytest.mark.asyncio
    async def test_get_recent_turns_few_messages(self, conv_store):
        """Small session reads all messages."""
        session_key = "user_123_2024-01-01"
        
        # Add a few turns
        for i in range(5):
            turn = ConversationTurn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        turns = await conv_store.get_recent_turns(123, session_key, limit=10)
        assert len(turns) == 5
        assert turns[0].content == "Message 0"
        assert turns[4].content == "Message 4"

    @pytest.mark.asyncio
    async def test_get_recent_turns_respects_limit(self, conv_store):
        """Limit parameter restricts returned turns."""
        session_key = "user_123_2024-01-01"
        
        # Add many turns
        for i in range(20):
            turn = ConversationTurn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        turns = await conv_store.get_recent_turns(123, session_key, limit=5)
        assert len(turns) == 5
        # Should be the LAST 5 messages
        assert turns[0].content == "Message 15"
        assert turns[4].content == "Message 19"

    @pytest.mark.asyncio
    async def test_get_recent_turns_large_file(self, conv_store):
        """Large files are read efficiently from the end."""
        session_key = "user_123_2024-01-01"
        
        # Add many turns to exceed the small file threshold
        for i in range(100):
            turn = ConversationTurn(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i} with some extra content to make it larger",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        turns = await conv_store.get_recent_turns(123, session_key, limit=10)
        assert len(turns) == 10
        # Should be the LAST 10 messages
        assert turns[0].content.startswith("Message 90")
        assert turns[9].content.startswith("Message 99")

    @pytest.mark.asyncio
    async def test_get_recent_turns_handles_corrupt_lines(self, conv_store, temp_sessions_dir):
        """Corrupt JSON lines are skipped gracefully."""
        session_key = "user_123_2024-01-01"
        
        # Add some valid turns
        for i in range(3):
            turn = ConversationTurn(
                role="user",
                content=f"Valid message {i}",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        # Manually append corrupt line
        path = os.path.join(temp_sessions_dir, f"{session_key}.jsonl")
        with open(path, "a") as f:
            f.write("this is not valid json\n")
        
        # Add more valid turns
        for i in range(3, 6):
            turn = ConversationTurn(
                role="user",
                content=f"Valid message {i}",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        turns = await conv_store.get_recent_turns(123, session_key, limit=10)
        # Should have 6 valid turns, corrupt line skipped
        assert len(turns) == 6

    @pytest.mark.asyncio
    async def test_get_recent_turns_concurrent_access(self, conv_store):
        """Concurrent reads don't interfere with each other."""
        session_key = "user_123_2024-01-01"
        
        # Add turns
        for i in range(10):
            turn = ConversationTurn(
                role="user",
                content=f"Message {i}",
            )
            await conv_store.append_turn(123, session_key, turn)
        
        # Concurrent reads
        async def read_turns():
            return await conv_store.get_recent_turns(123, session_key, limit=5)
        
        results = await asyncio.gather(*[read_turns() for _ in range(5)])
        
        # All reads should return same result
        for turns in results:
            assert len(turns) == 5
            assert turns[4].content == "Message 9"
