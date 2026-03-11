# User Story: Consistent Proactive Message Button UX

**Status:** ⬜ Backlog

## Summary
As a user, I want all proactive messages (briefings, reminders, check-ins) to use a
consistent action button layout so that Remy feels coherent rather than having some
triggers with buttons and others with none.

---

## Background

Proactive message UX is currently inconsistent: the morning briefing has snooze/calendar
buttons, some reminders have buttons, and afternoon/evening check-ins have none. The
button construction is also ad-hoc — each trigger builds its own `InlineKeyboardMarkup`
inline, with no shared factory.

Identified in Phase 3 item 12 of `docs/archive/consolidation-review-2026-03.md`.

Related to `US-working-message-normalisation.md` (consistent delivery mechanism) and
`US-proactive-prompt-consolidation.md` (consistent prompt builder).

---

## Acceptance Criteria

1. **Single `ProactiveKeyboard` factory** (or equivalent) produces `InlineKeyboardMarkup`
   for all proactive trigger types.
2. **All proactive triggers** (morning briefing, evening check-in, afternoon check-in,
   reminders) attach zero or more action buttons using the same factory — no special
   casing per trigger.
3. **Standard button set** for triggers that warrant it (at minimum: briefing, check-ins):
   - `✅ Done` — acknowledge / dismiss
   - `💤 Snooze 1h` — delay re-trigger (if snooze is supported)
4. **Reminder triggers** include a `✅ Done` button that marks the reminder complete.
5. **Callback handlers** for the new buttons are registered and functional.
6. **No regression** — existing buttons that already work continue to work.

---

## Implementation

**Files:** `remy/bot/proactive_keyboard.py` (new), `remy/bot/handlers/pipeline.py`
(or `remy/scheduler/pipeline.py`), `remy/bot/handlers/callbacks.py`

### Factory interface

```python
from enum import auto, Enum
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class ProactiveAction(Enum):
    DISMISS = auto()
    SNOOZE_1H = auto()
    SNOOZE_4H = auto()

def make_proactive_keyboard(
    actions: list[ProactiveAction],
    context_id: str | None = None,
) -> InlineKeyboardMarkup:
    """Build a standard proactive action keyboard."""
    ...
```

### Usage

```python
# In pipeline.py, for each trigger:
keyboard = make_proactive_keyboard(
    [ProactiveAction.DISMISS, ProactiveAction.SNOOZE_1H],
    context_id=f"briefing:{date.today()}",
)
await bot.send_message(chat_id, text, reply_markup=keyboard)
```

### Notes

- Snooze requires the scheduler to support re-scheduling a one-off trigger — check
  `ProactiveScheduler` API for existing support.
- `context_id` in the callback data allows the handler to know which trigger to dismiss
  or reschedule.
- Depends on `US-proactive-prompt-consolidation.md` being complete first (so all triggers
  pass through a single delivery path that can uniformly attach the keyboard).

---

## Test Cases

| Scenario | Expected |
|---|---|
| Morning briefing sent | `✅ Done` and `💤 Snooze 1h` buttons present |
| Evening check-in sent | At least `✅ Done` button present |
| Reminder sent | `✅ Done` button present; tapping marks reminder complete |
| `✅ Done` tapped | Message acknowledged; button removed or updated |
| `💤 Snooze 1h` tapped | Trigger re-fires after ~1 hour |
| Trigger with `actions=[]` | Message sent with no keyboard (no crash) |

---

## Out of Scope

- Redesigning the content of proactive messages
- Adding new proactive trigger types
- Snooze persistence across bot restarts (nice to have, deferred)
