# User Story: Normalise Working Message / Feedback Patterns

**Status:** ⬜ Backlog

## Summary
As a user, I want consistent visual feedback (typing indicators, "Working…" placeholders,
error presentation) regardless of which handler or tool triggered the response, so that
Remy feels coherent rather than patchy.

---

## Background

The working/typing indicator logic is currently scattered across at least four files:
`chat.py`, `pipeline.py`, `background.py`, and `streaming.py`. Each implements its own
version of "send placeholder → do work → edit to result". There is no shared abstraction,
so the UX varies: some paths show `_Working…_`, others show nothing, others use different
wording.

Identified in Phase 3 item 11 of `docs/archive/consolidation-review-2026-03.md`.

---

## Acceptance Criteria

1. **Single `WorkingMessage` async context manager** in a shared utility module
   (e.g. `remy/bot/working_message.py`).
2. **All message handling paths** (chat handler, proactive pipeline, background tasks)
   use `WorkingMessage` — no inline placeholder logic remains.
3. **Consistent copy:** placeholder text is `_Working…_`; tool-use indicator is
   `_⚙️ Using \<tool\>…_`; error presentation uses a uniform format.
4. **Graceful degradation:** if the placeholder message cannot be edited (e.g. deleted by
   user), no unhandled exception is raised.
5. **No regression in streaming behaviour** — streamed responses still update the message
   in place as chunks arrive.

---

## Implementation

**Files:** `remy/bot/working_message.py` (new), `remy/bot/handlers/chat.py`,
`remy/bot/handlers/pipeline.py` (or `remy/scheduler/pipeline.py`),
`remy/bot/handlers/background.py`, `remy/bot/streaming.py`

### WorkingMessage interface

```python
class WorkingMessage:
    """Async context manager that sends a placeholder and edits it on exit."""

    def __init__(self, message: telegram.Message, initial: str = "_Working…_"):
        ...

    async def __aenter__(self) -> "WorkingMessage":
        self._sent = await message.reply_text(self.initial, parse_mode="Markdown")
        return self

    async def set_status(self, text: str) -> None:
        """Update the placeholder mid-task (e.g. tool name)."""
        await self._sent.edit_text(text, parse_mode="Markdown")

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            await self._sent.edit_text("⚠️ Something went wrong. Check /logs.")
        # Caller is responsible for editing with final content if no exception.
```

### Usage pattern

```python
async with WorkingMessage(update.message) as wm:
    await wm.set_status("_⚙️ Using calendar…_")
    result = await do_work()
await wm._sent.edit_text(result, parse_mode="Markdown")
```

### Notes

- Audit each existing placeholder pattern to ensure consistent replacement.
- The `streaming.py` path is more complex (incremental edits) — `WorkingMessage` may only
  wrap the initial placeholder; the streaming loop edits independently.

---

## Test Cases

| Scenario | Expected |
|---|---|
| Normal tool call | `_Working…_` placeholder sent; edited to result on completion |
| Tool name known mid-task | Status updates to `_⚙️ Using calendar…_` |
| Exception raised inside context | Placeholder edited to error message; no crash |
| User deletes placeholder before edit | `MessageNotModified` / `BadRequest` caught; no crash |
| Proactive briefing | Same `_Working…_` pattern as chat handler |

---

## Out of Scope

- Proactive button UX (separate story: `US-proactive-button-consistency.md`)
- Streaming implementation details beyond the initial placeholder
