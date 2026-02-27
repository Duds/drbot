"""Tests for remy/ai/classifier.py — no network required."""

import pytest
from remy.ai.classifier import MessageClassifier


@pytest.fixture
def classifier():
    # No claude_client — only tests fast-path heuristics
    return MessageClassifier(claude_client=None)


@pytest.mark.asyncio
async def test_greeting_is_routine(classifier):
    assert await classifier.classify("hi") == "routine"
    assert await classifier.classify("Hello!") == "routine"
    assert await classifier.classify("thanks") == "routine"


@pytest.mark.asyncio
async def test_short_no_keywords_is_routine(classifier):
    assert await classifier.classify("What time is it?") == "routine"
    assert await classifier.classify("How are you?") == "routine"


@pytest.mark.asyncio
async def test_code_keywords_are_coding(classifier):
    assert await classifier.classify("Write a Python function to sort a list") == "coding"
    assert await classifier.classify("Refactor this module") == "coding"
    assert await classifier.classify("Debug this error in my code") == "coding"


@pytest.mark.asyncio
async def test_file_extensions_are_coding(classifier):
    assert await classifier.classify("Update app.py to add logging") == "coding"
    assert await classifier.classify("Fix the bug in index.ts") == "coding"


@pytest.mark.asyncio
async def test_code_fence_is_coding(classifier):
    assert await classifier.classify("```python\nprint('hi')\n```") == "coding"


@pytest.mark.asyncio
async def test_git_keywords_are_coding(classifier):
    assert await classifier.classify("git commit all changes") == "coding"
    assert await classifier.classify("Deploy to production") == "coding"


@pytest.mark.asyncio
async def test_ambiguous_long_message_defaults_reasoning(classifier):
    # No client + ambiguous → defaults to "reasoning"
    long_msg = "I was wondering if you could help me think through my strategy " * 5
    result = await classifier.classify(long_msg)
    assert result == "reasoning"
