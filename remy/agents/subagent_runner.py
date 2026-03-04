"""
Subagent runner — invokes heavy tasks (board, research, retrospective) and delivers
results via the same path as BackgroundTaskRunner (send_message + job_store).

Remy's handlers only: validate input, create job, show working state, invoke the runner,
and return. The runner starts the subagent (in-process BoardOrchestrator for the first
milestone; SDK or dedicated process later) and on completion calls back to deliver.

See docs/backlog/US-subagents-next-plan.md and docs/architecture/remy-ui-and-subagent-boundary.md.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .background import BackgroundTaskRunner
    from .orchestrator import BoardOrchestrator

logger = logging.getLogger(__name__)


class SubagentRunner:
    """
    Thin runner that accepts task parameters and starts the appropriate subagent.
    On completion, delivery is done by the provided BackgroundTaskRunner (set_running,
    set_done/set_failed, send_message, working_message.stop).
    """

    def __init__(self, board_orchestrator: "BoardOrchestrator | None" = None) -> None:
        self._board_orchestrator = board_orchestrator

    def start_board(
        self,
        background_runner: "BackgroundTaskRunner",
        topic: str,
        user_context: str,
        user_id: int,
        session_key: str,
    ) -> None:
        """
        Start a board analysis subagent. Schedules the work on the given
        BackgroundTaskRunner and returns immediately; the runner delivers the
        result when the subagent completes.
        """
        if self._board_orchestrator is None:
            raise RuntimeError(
                "Board subagent not available — board_orchestrator not configured."
            )
        coro = self._board_coro(
            topic=topic,
            user_context=user_context,
            user_id=user_id,
            session_key=session_key,
        )
        asyncio.create_task(background_runner.run(coro, label="board analysis"))

    async def _board_coro(
        self,
        topic: str,
        user_context: str,
        user_id: int,
        session_key: str,
    ) -> str:
        """Produce the full board report (streaming collected). Used by start_board."""
        board = self._board_orchestrator
        if board is None:
            raise RuntimeError("Board subagent not available.")
        chunks = [f"🏛 *Board of Directors: {topic}*\n\n"]
        async for chunk in board.run_board_streaming(
            topic,
            user_context,
            user_id=user_id,
            session_key=session_key,
        ):
            chunks.append(chunk)
        return "".join(chunks)
