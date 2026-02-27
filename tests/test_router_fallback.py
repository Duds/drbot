"""
Tests for preserving conversation history during Ollama fallback in ModelRouter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from remy.ai.router import ModelRouter

@pytest.mark.asyncio
async def test_stream_with_fallback_passes_history_to_ollama():
    # 1. Setup mocks
    claude = MagicMock()
    import anthropic
    # Claude fails with an API error to trigger fallback
    claude.stream_message = MagicMock(side_effect=anthropic.APIStatusError("Claude API Down", response=MagicMock(), body=None))
    
    mistral = MagicMock()
    moonshot = MagicMock()
    ollama = MagicMock()
    ollama.is_available = AsyncMock(return_value=True)
    # Ollama succeeds
    async def fake_stream(*args, **kwargs):
        yield "Ollama response"
    ollama.stream_chat = MagicMock(side_effect=fake_stream)
    
    router = ModelRouter(claude, mistral, moonshot, ollama)
    
    # 2. Test data
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "Tell me a joke."},
    ]
    
    # 3. Execution
    responses = []
    async for chunk in router.stream("Tell me a joke.", messages, user_id=1):
        responses.append(chunk)
    
    # 4. Assertions
    # Ensure Claude was called first (since "Tell me a joke" is routine and short)
    # Wait, "Tell me a joke" might be classified as routine.
    # If routine and < 50k tokens, it calls mistral.
    # Let's mock mistral to fail.
    mistral.stream_chat = MagicMock(side_effect=anthropic.APIStatusError("Mistral Down", response=MagicMock(), body=None))

    # Re-run with mistral failing
    responses = []
    async for chunk in router.stream("Tell me a joke.", messages, user_id=1):
        responses.append(chunk)

    # Ensure Ollama was called with the FULL history
    ollama.stream_chat.assert_called()
    call_args, call_kwargs = ollama.stream_chat.call_args
    assert call_args[0] == messages
    assert "Ollama response" in "".join(responses)
    assert "Mistral unavailable" in "".join(responses)
