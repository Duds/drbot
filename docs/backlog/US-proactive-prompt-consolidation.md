# User Story: Consolidate Proactive System Prompt Functions

**Status:** ⬜ Backlog

## Summary
As a developer, I want the five near-identical proactive system prompt builder functions
collapsed into one parameterised function so that changes to the prompt structure only
need to be made in one place.

---

## Background

`pipeline.py` contains five functions with the same shape
(`{SOUL.md} + "---" + scenario text + JSON context`):

- `_reminder_system_prompt(label)`
- `_briefing_system_prompt(context)`
- `_evening_checkin_system_prompt(context)`
- `_afternoon_checkin_system_prompt(context)`
- `_afternoon_check_system_prompt(context)` *(possible duplicate of the above)*

These are not substantially different. Any change to the shared structure (e.g. injecting
a new memory block) must be made five times, and it often isn't. Identified in Phase 2
item 7 of `docs/archive/consolidation-review-2026-03.md`.

---

## Acceptance Criteria

1. **Single `build_proactive_system_prompt(scenario: str, context: dict | None = None)`
   function** replaces all five.
2. **Each proactive trigger passes a scenario string** and an optional context dict.
   The function composes the full system prompt identically to the current per-function
   output.
3. **All five call sites updated** to use the new function.
4. **Output is behaviourally identical** to the previous per-function output for each
   scenario — no change to what Claude receives.
5. **No duplicate `_afternoon_*` functions** — if there are two, consolidate to one
   (or remove the dead one).

---

## Implementation

**Files:** `remy/bot/handlers/pipeline.py` (or `remy/scheduler/pipeline.py`)

### New function signature

```python
async def build_proactive_system_prompt(
    scenario: str,
    context: dict | None = None,
) -> str:
    soul = await load_soul()
    context_block = json.dumps(context, indent=2) if context else ""
    return f"{soul}\n---\n{scenario}\n{context_block}".strip()
```

### Call sites (before → after)

```python
# Before
system = await _briefing_system_prompt(briefing_context)

# After
system = await build_proactive_system_prompt(
    scenario=BRIEFING_SCENARIO_TEXT,
    context=briefing_context,
)
```

Define `BRIEFING_SCENARIO_TEXT`, `REMINDER_SCENARIO_TEXT`, etc. as module-level constants
so the scenario copy is still easy to find and edit.

### Notes

- Read the current five functions carefully before writing the unified version — ensure
  the scenario text is preserved exactly (it drives Claude's behaviour).
- If `_afternoon_check_system_prompt` and `_afternoon_checkin_system_prompt` are true
  duplicates, remove one and update its single call site.

---

## Test Cases

| Scenario | Expected |
|---|---|
| `build_proactive_system_prompt("briefing", ctx)` | Output matches former `_briefing_system_prompt(ctx)` |
| `build_proactive_system_prompt("reminder", None)` | Output matches former `_reminder_system_prompt(label)` structure |
| `context=None` | No JSON block appended; no crash |
| Proactive triggers fire in scheduler | Same Claude behaviour as before |

---

## Out of Scope

- Changing the content of scenario prompts (only restructuring the builder)
- Consistent proactive button UX (separate story: `US-proactive-button-consistency.md`)
