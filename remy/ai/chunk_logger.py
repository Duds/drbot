"""
Optional chunk logger: writes every stream event and tool invocation to a JSONL file.

When chunk_log_enabled is True, logs:
  - session_start: user message preview, user_id, chat_id, message_id
  - text_chunk: text length or truncation
  - tool_status: tool_name, tool_use_id (model requested a tool)
  - tool_invoke: tool_name, tool_use_id, tool_input (right before dispatch)
  - tool_result: tool_name, tool_use_id, result length
  - tool_turn_complete: num assistant blocks, num result blocks
  - hand_off: topic (max_iterations → Board)
  - board_agent: agent name, phase (start|done)

Enables observability of which agents are called, sends, replies, and tools.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

# Truncation limits for log payloads
_MAX_TEXT_LOG = 200
_MAX_RESULT_LOG = 500
_MAX_INPUT_KEYS = 20
_MAX_INPUT_VAL = 100


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _truncate_dict(
    d: dict[str, Any], max_keys: int = _MAX_INPUT_KEYS, max_val: int = _MAX_INPUT_VAL
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(d.items()):
        if i >= max_keys:
            out["_truncated_keys"] = len(d) - max_keys
            break
        if isinstance(v, str) and len(v) > max_val:
            out[k] = _truncate(v, max_val)
        elif isinstance(v, dict):
            out[k] = _truncate_dict(v, max_keys=5, max_val=50)
        else:
            out[k] = v
    return out


def _chunk_log_path() -> str:
    s = get_settings()
    if s.chunk_log_path:
        return s.chunk_log_path
    return os.path.join(s.logs_dir, "chunk_log.jsonl")


def _write_line(record: dict[str, Any]) -> None:
    try:
        s = get_settings()
        if not s.chunk_log_enabled:
            return
        path = _chunk_log_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.debug("chunk_log write failed: %s", e)


def _base_context(
    user_id: int | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    iteration: int | None = None,
    agent: str = "main",
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
    }
    if user_id is not None:
        ctx["user_id"] = user_id
    if chat_id is not None:
        ctx["chat_id"] = chat_id
    if message_id is not None:
        ctx["message_id"] = message_id
    if iteration is not None:
        ctx["iteration"] = iteration
    return ctx


def log_session_start(
    *,
    user_id: int,
    chat_id: int | None = None,
    message_id: int | None = None,
    message_preview: str = "",
) -> None:
    record = _base_context(user_id=user_id, chat_id=chat_id, message_id=message_id)
    record["event"] = "session_start"
    record["message_preview"] = _truncate(message_preview or "", _MAX_TEXT_LOG)
    _write_line(record)


def log_stream_event(
    event: Any,
    *,
    user_id: int,
    chat_id: int | None = None,
    message_id: int | None = None,
    iteration: int | None = None,
) -> None:
    """Log one StreamEvent (TextChunk, ToolStatusChunk, etc.)."""
    s = get_settings()
    if not s.chunk_log_enabled:
        return
    record = _base_context(
        user_id=user_id, chat_id=chat_id, message_id=message_id, iteration=iteration
    )
    event_type = type(event).__name__
    if event_type == "TextChunk":
        record["event"] = "text_chunk"
        record["text_len"] = len(event.text)
        record["text_preview"] = _truncate(event.text, _MAX_TEXT_LOG)
    elif event_type == "ToolStatusChunk":
        record["event"] = "tool_status"
        record["tool_name"] = event.tool_name
        record["tool_use_id"] = event.tool_use_id
    elif event_type == "ToolResultChunk":
        record["event"] = "tool_result"
        record["tool_name"] = event.tool_name
        record["tool_use_id"] = event.tool_use_id
        record["result_len"] = len(event.result)
        record["result_preview"] = _truncate(event.result, _MAX_RESULT_LOG)
    elif event_type == "ToolTurnComplete":
        record["event"] = "tool_turn_complete"
        record["assistant_blocks"] = len(event.assistant_blocks)
        record["tool_result_blocks"] = len(event.tool_result_blocks)
    elif event_type == "HandOffToSubAgent":
        record["event"] = "hand_off"
        record["topic"] = event.topic
    else:
        record["event"] = event_type.lower()
    _write_line(record)


def log_tool_invoke(
    *,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, Any],
    user_id: int,
    chat_id: int | None = None,
    message_id: int | None = None,
    iteration: int | None = None,
) -> None:
    """Log immediately before dispatching a tool (includes tool_input)."""
    record = _base_context(
        user_id=user_id, chat_id=chat_id, message_id=message_id, iteration=iteration
    )
    record["event"] = "tool_invoke"
    record["tool_name"] = tool_name
    record["tool_use_id"] = tool_use_id
    record["tool_input"] = _truncate_dict(tool_input)
    _write_line(record)


def log_board_agent(
    *,
    agent_name: str,
    phase: str,
    user_id: int | None = None,
) -> None:
    """Log Board of Directors sub-agent start or done."""
    record = _base_context(user_id=user_id or 0, agent="board")
    record["event"] = "board_agent"
    record["board_agent"] = agent_name
    record["phase"] = phase  # "start" | "done"
    _write_line(record)
