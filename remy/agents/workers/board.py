"""Board worker — runs the Board of Directors as a TaskRunner worker (SAD v10 §11).

Wraps BoardOrchestrator.run_board() so the board analysis goes through the
same task manifest → synthesis → heartbeat → Remy path as all other workers.

Before this change, exec_run_board returned the raw board report directly as a
tool result, bypassing Remy's personal context layer entirely. Now:

  exec_run_board → TaskRunner.spawn("board", {topic}) → BoardWorker
  → BoardOrchestrator.run_board() → raw report stored in agent_tasks.result
  → TaskOrchestrator synthesises → heartbeat → Remy layers personal context
  → Dale sees Remy's framed summary, not a raw multi-agent dump

Input task_context keys:
  topic       (str, required) — the question or topic for the board
  user_id     (int, optional) — for api_calls logging in the orchestrator
  session_key (str, optional) — for api_calls logging in the orchestrator

Output: raw board report string (synthesis happens in TaskOrchestrator)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...memory.database import DatabaseManager
    from ..orchestrator import BoardOrchestrator

logger = logging.getLogger(__name__)


class BoardWorker:
    """
    Runs the Board of Directors analysis and returns the raw report.

    The BoardOrchestrator is injected at construction time via TaskRunner.
    TaskOrchestrator handles synthesis; this worker only executes.
    """

    def __init__(
        self,
        db: "DatabaseManager",
        board_orchestrator: "BoardOrchestrator",
    ) -> None:
        self._db = db
        self._board = board_orchestrator

    async def run(
        self,
        task_id: str,
        task_context: dict,
        skill_context: str = "",
    ) -> str:
        topic = (task_context.get("topic") or "").strip()
        if not topic:
            return "Board: no topic provided."

        user_id = task_context.get("user_id", 0)
        session_key = task_context.get("session_key", f"board-{task_id[:8]}")

        logger.info("BoardWorker task_id=%s topic=%r", task_id, topic[:80])

        # run_board returns the full formatted report as a string
        report = await self._board.run_board(
            topic,
            user_id=user_id,
            session_key=session_key,
        )
        return report
