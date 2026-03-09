"""
Unified "working" placeholder for long-running operations.

Phase 3.11: Single abstraction for "show placeholder, optionally animate, edit or replace".
Used by chat, pipeline, background tasks, and admin handlers.

Usage (background — delete placeholder, send new message)::

    async with working_message(bot, chat_id, thread_id=thread_id) as wm:
        result = await long_operation(...)
    await bot.send_message(chat_id, result)

Usage (edit-in-place — caller edits the message)::

    async with working_message(bot, chat_id, animate=True) as wm:
        await stream_into(wm.message)  # or wm.edit_to_result(text)
"""

import asyncio
import itertools
import logging
import random

logger = logging.getLogger(__name__)

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
        initial_text: str = "⚙️ …",
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

    async def start(self) -> None:
        """Send the initial placeholder and optionally start the animation loop."""
        try:
            kwargs: dict = {"message_thread_id": self._thread_id}
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
            except Exception as e:
                logger.debug("WorkingMessage edit_to_result failed: %s", e)

    async def __aenter__(self) -> "WorkingMessage":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
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
                except Exception as e:
                    logger.debug("WorkingMessage edit failed: %s", e)
                await asyncio.sleep(_EDIT_INTERVAL)
