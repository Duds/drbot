"""
Unified "working" placeholder for long-running operations.

Phase 3.11 / US-working-message-normalisation: Single abstraction for
"show placeholder, optionally animate, edit or replace". Consistent copy
and graceful degradation when the placeholder cannot be edited.
"""

import asyncio
import itertools
import logging
import random

logger = logging.getLogger(__name__)

try:
    from telegram.error import BadRequest
except ImportError:
    BadRequest = Exception  # type: ignore[misc, assignment]

# Standardised copy (US-working-message-normalisation)
WORKING_PLACEHOLDER = "_Working…_"
ERROR_PLACEHOLDER = "⚠️ Something went wrong. Check /logs."


def tool_status_text(tool_name: str) -> str:
    """Format for mid-task tool indicator. Use when tool name is known."""
    return f"_⚙️ Using {tool_name}…_"


_PHRASES = [
    "Reticulating splines",
    "Homologating girdles",
    "Consulting the oracle",
    "Polishing the chrome",
    "Herding cats",
    "Aligning the stars",
    "Buffering logic",
    "Generating excuses",
    "Reheating the coffee",
    "Calibrating flux capacitors",
    "Defragmenting the ether",
    "Downloading more RAM",
    "Appeasing the compiler gods",
    "Untangling the time stream",
    "Reversing the polarity",
    "Consulting the runes",
    "Spinning up the hamster wheel",
    "Charging the crystals",
    "Negotiating with the cloud",
    "Warming up the neurons",
    "Bribing the algorithms",
    "Summoning the data spirits",
    "Polishing the pixels",
    "Tuning the quantum harmonics",
    "Feeding the gremlins",
]

_EDIT_INTERVAL = 1.2  # seconds between edits — well under Telegram's rate limit


class WorkingMessage:
    """
    Unified placeholder for long-running operations.

    Supports two modes:
    - background: animate, then delete on stop() (caller sends new message)
    - edit-in-place: animate until edit_to_result() or caller edits message directly
    """

    def __init__(
        self,
        bot,
        chat_id: int,
        thread_id: int | None = None,
        *,
        initial_text: str = WORKING_PLACEHOLDER,
        animate: bool = True,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._thread_id = thread_id
        self._initial_text = initial_text
        self._do_animate = animate
        self._message = None
        self._message_id: int | None = None
        self._task: asyncio.Task | None = None
        self._replaced = False

    @property
    def message(self):
        """The sent Telegram message object (for caller to edit directly)."""
        return self._message

    def mark_replaced(self) -> None:
        """Mark the message as replaced so __aexit__ does not delete it."""
        self._replaced = True

    async def set_status(self, text: str, parse_mode: str = "Markdown") -> None:
        """Update the placeholder mid-task (e.g. tool name). Graceful on edit failure."""
        if not self._message_id:
            return
        try:
            await self._bot.edit_message_text(
                text, self._chat_id, self._message_id, parse_mode=parse_mode
            )
        except BadRequest as e:
            logger.debug(
                "WorkingMessage set_status edit failed (e.g. message deleted): %s", e
            )
        except Exception as e:
            logger.debug("WorkingMessage set_status failed: %s", e)

    async def start(self) -> None:
        """Send the initial placeholder and optionally start the animation loop."""
        try:
            kwargs: dict = {"message_thread_id": self._thread_id}
            if self._initial_text.startswith("_") and self._initial_text.endswith("_"):
                kwargs["parse_mode"] = "Markdown"
            msg = await self._bot.send_message(
                self._chat_id,
                self._initial_text,
                **kwargs,
            )
            self._message = msg
            self._message_id = msg.message_id
            if self._do_animate:
                self._task = asyncio.create_task(self._animate_loop())
        except Exception as e:
            logger.debug("WorkingMessage failed to start: %s", e)

    async def stop(self, *, delete: bool = True) -> None:
        """Cancel animation and optionally delete the placeholder message."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if delete and self._message_id and not self._replaced:
            try:
                await self._bot.delete_message(self._chat_id, self._message_id)
            except Exception as e:
                logger.debug("WorkingMessage failed to delete: %s", e)
            self._message_id = None

    async def edit_to_result(self, text: str, parse_mode: str = "Markdown") -> None:
        """Stop animation and edit the message to the final result."""
        self._replaced = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._message_id:
            try:
                await self._bot.edit_message_text(
                    text, self._chat_id, self._message_id, parse_mode=parse_mode
                )
            except BadRequest as e:
                logger.debug(
                    "WorkingMessage edit_to_result failed (e.g. message deleted): %s", e
                )
            except Exception as e:
                logger.debug("WorkingMessage edit_to_result failed: %s", e)

    async def __aenter__(self) -> "WorkingMessage":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type and self._message_id and not self._replaced:
            try:
                await self._bot.edit_message_text(
                    ERROR_PLACEHOLDER,
                    self._chat_id,
                    self._message_id,
                    parse_mode="Markdown",
                )
            except (BadRequest, Exception) as e:
                logger.debug("WorkingMessage error placeholder edit failed: %s", e)
        await self.stop(delete=not self._replaced)

    async def _animate_loop(self) -> None:
        """Cycle through phrases with a typewriter effect."""
        shuffled = _PHRASES.copy()
        random.shuffle(shuffled)

        for phrase in itertools.cycle(shuffled):
            for suffix in ("▌", "…"):
                try:
                    await self._bot.edit_message_text(
                        f"⚙️ {phrase}{suffix}",
                        self._chat_id,
                        self._message_id,
                    )
                except BadRequest:
                    pass  # e.g. message deleted by user
                except Exception as e:
                    logger.debug("WorkingMessage edit failed: %s", e)
                await asyncio.sleep(_EDIT_INTERVAL)
