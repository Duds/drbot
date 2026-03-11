# User Story: Reduce Telegram Command Surface

**Status:** ⬜ Backlog

## Summary
As a user, I want Remy's command list to be short and focused so that `/help` is actually
useful and I can access everything else via natural language.

---

## Background

Remy currently exposes ~50 slash commands. Most duplicate a native tool capability —
`/calendar` does the same thing as asking "what's on my calendar?", `/goals` the same as
"what are my goals?", etc. This creates two maintenance burdens per capability and a
`/help` response that is too long to read.

The consolidation review (Phase 3 item 10, `docs/archive/consolidation-review-2026-03.md`)
proposes reducing to ≤15 commands. Commands that genuinely benefit from explicit invocation
(async tasks, privacy ops, system controls) are kept; everything with a natural-language
equivalent is removed.

---

## Acceptance Criteria

1. **≤15 registered commands** after reduction.
2. **Kept commands** (minimum set):
   - `/start` — greeting and brief capability overview (3–4 lines)
   - `/cancel` — stop current task
   - `/briefing` — trigger morning briefing now
   - `/status` — system health summary
   - `/setmychat` — register proactive message target
   - `/compact` — compress conversation history
   - `/delete_conversation` — clear history
   - `/board <topic>` — Board of Directors analysis
   - `/diagnostics` — comprehensive self-check
   - `/logs [filter]` — raw log access
   - `/stats [period]` — usage stats
   - `/costs` — API cost summary
3. **Removed commands** no longer appear in `/help` or BotFather command list.
4. **Removed commands** return a helpful redirect message if a user tries to invoke them
   (e.g. "Use natural language — just ask me about your calendar directly.").
5. **No tool functionality removed.** Every removed command's capability remains accessible
   via the existing tool (natural language).
6. **`/help` response fits in a single Telegram message** (≤4096 chars) without truncation.

---

## Implementation

**Files:** `remy/bot/handlers/` (various command handlers), `remy/bot/handlers/__init__.py`
or `make_handlers()` registration, `remy/bot/telegram_app.py` (or equivalent registration
file), BotFather command list update.

### Approach

1. Audit all registered commands. Map each to: keep / redirect / remove.
2. For commands being removed: replace the handler body with a single `reply_text()` that
   tells the user to ask naturally, then unregister from the dispatcher.
3. Update the `/start` and `/help` handlers to reflect the new short command list.
4. Submit updated command list to BotFather via `set_my_commands` API call or update the
   registration in code.

### Commands to remove (examples — audit required)

```
/gmail-unread, /gmail-classify, /calendar, /goals, /plans,
/contacts, /search, /grocery, /bookmarks, /research,
/retrospective, /consolidate, /relay, /automations, /reminders,
/facts, /knowledge, /read, /write, /ls, /find, /set_project,
/project_status, /python, /ollama, ...
```

### Notes

- Audit `make_handlers()` return dict to get the authoritative command list.
- Some commands (e.g. `/read`, `/write`) may be used by power users who expect them.
  Consider a deprecation message period before full removal.
- Depends on all tool capabilities being reachable via natural language — verify there are
  no tool gaps before removing commands.

---

## Test Cases

| Scenario | Expected |
|---|---|
| `/help` | Single message, ≤15 commands listed |
| `/calendar` (removed) | Redirect: "Ask me naturally about your calendar" |
| "what's on my calendar tomorrow?" | Calendar tool called; results returned |
| `/briefing` (kept) | Morning briefing triggered as before |
| `/cancel` (kept) | Current task cancelled as before |

---

## Out of Scope

- Changing the underlying tool implementations
- Removing any tool from `TOOL_SCHEMAS`
- Changes to proactive message UX (separate story: `US-working-message-normalisation.md`)
