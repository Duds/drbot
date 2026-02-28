# Remy Bug Report

_Last updated: see file history_

---

## Bug 1: ConversationStore missing `sessionsdir`

- **Symptom:** `'ConversationStore' object has no attribute 'sessionsdir'`
- **Impact:** Conversation history not saving/loading between sessions. Context is lost on restart.
- **Likely cause:** Attribute renamed or removed from `ConversationStore` class without updating all references.
- **Priority:** High
- **Status:** ✅ Fixed
- **Fix:** Changed `self._conv_store._sessions_dir` to `self._conv_store.sessions_dir` in `remy/diagnostics/runner.py`

---

## Bug 2: Diagnostics import failure — `_since_dt`

- **Symptom:** `cannot import name '_since_dt' from 'remy.diagnostics'` (`/app/remy/diagnostics/__init__.py`)
- **Impact:** `/logs` tool completely broken — no ability to self-diagnose from inside a conversation.
- **Likely cause:** `_since_dt` was defined somewhere and removed or moved without updating the import.
- **Priority:** High
- **Status:** ✅ Fixed
- **Fix:** Added `_since_dt` to imports and `__all__` in `remy/diagnostics/__init__.py`

---

## Bug 3: `set_proactive_chat` tool not working via natural language

- **Symptom:** Tool call returns failure — requires Telegram chat context not available in tool context.
- **Impact:** Setting proactive chat via conversation doesn't work; `/setmychat` command required instead.
- **Priority:** Medium
- **Status:** ✅ Fixed
- **Fix:** Added `chat_id` parameter threading through `dispatch()` → `stream_with_tools()` → `_stream_with_tools_path()`. The `set_proactive_chat` tool now receives the chat context and can save the primary chat ID directly.

---

## Bug 4: `/privacy-audit` command uses invalid `stream_with_tools` parameters

- **Symptom:** `/privacy-audit` command likely fails or behaves unexpectedly
- **Impact:** Privacy audit feature broken
- **Location:** `remy/bot/handlers.py` lines 2037–2043
- **Likely cause:** The call uses parameters (`tools`, `tool_executor`, `max_tokens`) that don't exist in the `stream_with_tools()` signature. The correct parameters are `tool_registry` and `user_id`.
- **Priority:** Medium
- **Status:** ✅ Fixed
- **Fix:** Updated `stream_with_tools()` call to use correct parameters: `tool_registry`, `user_id`, and `system` instead of the non-existent `tools`, `tool_executor`, and `max_tokens`.

---

## Bug 5: Markdown rendering broken in summary/recap messages

- **Symptom:** Markdown formatting (bold, italic, etc.) appears as raw symbols rather than rendered text in Telegram — e.g. `*text*` instead of **text**
- **Impact:** Recap and summary-style responses are visually noisy and hard to read
- **Likely cause:** MarkdownV2 special characters not being escaped correctly, or messages being sent with the wrong `parse_mode` (or none at all) in certain code paths
- **Priority:** Medium
- **Status:** ⬜ Open
- **Reported:** 2026-03-01

---

## Bug 6: Telegram transient disconnections causing slow responses

- **Symptom:** `httpx.RemoteProtocolError: Server disconnected without sending a response` logged as warnings during active conversations
- **Impact:** Responses are delayed while the bot retries the Telegram connection. From the user's perspective, Remy appears slow or unresponsive.
- **Likely cause:** Telegram's long-polling connection dropping unexpectedly; retry logic may be adding latency before re-establishing.
- **Priority:** Medium
- **Status:** ⬜ Open
- **Reported:** 2026-02-28

---

## Bug 7: Scheduled job missed on startup — fires with large delay

- **Symptom:** `Run time of job "ProactiveScheduler._register_automation_job" was missed by 6:56:53` logged on startup
- **Impact:** Scheduled automations (e.g. 1pm reminders) are silently skipped if the bot was down when they were due to fire. No catch-up or notification to the user.
- **Likely cause:** APScheduler's `misfire_grace_time` is either too short or not configured — missed jobs are dropped rather than caught up or flagged.
- **Priority:** Medium
- **Status:** ⬜ Open
- **Reported:** 2026-02-28
