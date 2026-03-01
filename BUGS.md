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
- **Root cause:** Two delivery paths used the wrong format mode:
  1. `chat.py` `_stream_with_tools_path._flush_display()` sent raw Claude text with `parse_mode="Markdown"` (old mode, no escaping)
  2. `proactive.py` `_send()` also used `parse_mode="Markdown"` with unescaped Claude output
- **Priority:** Medium
- **Status:** ✅ Fixed
- **Fix:**
  - `chat.py`: Added `format_telegram_message()` import and changed `_flush_display()` to use `format_telegram_message(truncated)` + `parse_mode="MarkdownV2"` with plain-text fallback
  - `proactive.py`: Added `format_telegram_message()` import; `_send()` now formats with MarkdownV2 and falls back to plain text on failure
- **Reported:** 2026-03-01

---

## Bug 6: Telegram transient disconnections causing slow responses

- **Symptom:** `httpx.RemoteProtocolError: Server disconnected without sending a response` logged as warnings during active conversations
- **Impact:** Responses are delayed while the bot retries the Telegram connection. From the user's perspective, Remy appears slow or unresponsive.
- **Root cause:** `ApplicationBuilder` defaults to HTTP/2 (via `httpx`). When the Telegram server drops the multiplexed TCP connection, the entire HTTP/2 stream is lost and reconnecting requires ALPN negotiation. HTTP/1.1 reconnects faster.
- **Priority:** Medium
- **Status:** ✅ Fixed
- **Fix:** Added `.http_version("1.1")` to the `ApplicationBuilder` chain in `remy/bot/telegram_bot.py`. HTTP/1.1 connections drop cleanly and reconnect without TLS renegotiation overhead.
- **Reported:** 2026-02-28

---

## Bug 7: Scheduled job missed on startup — fires with large delay

- **Symptom:** `Run time of job "ProactiveScheduler._register_automation_job" was missed by 6:56:53` logged on startup
- **Impact:** Without `coalesce=True`, if the bot was down across multiple fire times, APScheduler would queue all missed runs and fire them in rapid succession on restart, causing message floods.
- **Root cause:** All `add_job()` calls had `misfire_grace_time=3600` but were missing `coalesce=True`. The default `coalesce=False` allows multiple rapid catch-up fires.
- **Priority:** Medium
- **Status:** ✅ Fixed
- **Fix:** Added `coalesce=True` to all 7 `add_job()` calls in `remy/scheduler/proactive.py` (morning_briefing, afternoon_focus, evening_checkin, monthly_retrospective, reindex_files, end_of_day_consolidation, automation jobs). If a job misfired multiple times while the bot was down, it now fires at most once on catch-up.
- **Reported:** 2026-02-28

---

## Bug 8: Memory injection fails on long fact content used as path

- **Symptom:** `[Errno 36] File name too long` when injecting memory context
- **Impact:** Memory injection fails entirely, Remy runs without memory context injected into prompts
- **Likely cause:** `_get_project_context()` in `injector.py` treats fact content as a directory path without validating it's actually a path. Long descriptions stored with `category: "project"` cause OS filename length errors.
- **Priority:** High
- **Status:** ✅ Fixed
- **Fix:** Added validation in `_get_project_context()` to skip content that doesn't start with `/` or exceeds 255 characters. Added unit tests.
- **Reported:** 2026-02-28

---

## Bug 10: Responses end mid-sentence with trailing "…"

- **Symptom:** Remy's response appears cut off mid-sentence, ending with "…" (or " …")
- **Impact:** Looks like Remy didn't finish her thought; confusing for the user
- **Root cause 1 (primary):** In `StreamingReply._edit_or_skip()` and `_flush_display()` in the tool path, all exceptions are silently caught. When a transient Telegram disconnection (Bug 6) hits at the moment of the *final* edit — the one that strips the in-progress " …" streaming indicator — the exception is swallowed and the message is left displaying `"partial text …"`.
- **Root cause 2 (secondary):** When Claude ends with a tool call and produces no text afterward, `_flush_display(final=True)` returns early because `current_display` is empty — leaving `"_⚙️ Using tool_name…_"` as the final message.
- **Locations:**
  - `remy/bot/streaming.py` — `finalize()` / `_edit_or_skip()`
  - `remy/bot/handlers/chat.py` — `_stream_with_tools_path()` → `_flush_display()`
- **Priority:** High
- **Status:** ✅ Fixed
- **Fix:**
  - `streaming.py`: `finalize()` retries `_flush()` once (0.5s delay) if `_last_sent` still ends with " …" after the first attempt
  - `chat.py`: retry `_flush_display(final=True)` once after 0.3s when there is text to show; if `current_display` is empty after tool turns, replace tool status message with "✓"
- **Reported:** 2026-03-01

---

## Bug 9: SQLite database corruption (knowledge table)

- **Symptom:** `database disk image is malformed (11)` errors; `PRAGMA integrity_check` shows btreeInitPage errors
- **Impact:** Knowledge table data (facts, goals) appeared corrupted — content columns showing NULL. Memory system non-functional.
- **Root cause:** Stale WAL pages left over from a previous crash. WAL mode without a startup checkpoint allows corrupt/incomplete journal frames to persist across restarts.
- **Priority:** Critical
- **Status:** ✅ Fixed (recovered + preventive measure added)
- **Fix:**
  - Database self-recovered (WAL auto-recovery on reconnect). `PRAGMA integrity_check` now returns `ok`; 37 facts + 6 goals are accessible.
  - Preventive fix added: `DatabaseManager.init()` in `remy/memory/database.py` now runs `PRAGMA wal_checkpoint(RESTART)` after DDL on every startup. This flushes any stale WAL frames to the main database file before serving requests. Non-fatal — wrapped in try/except so a checkpoint failure does not block startup.
- **Reported:** 2026-03-01

---

## Bug 11: Conversation context lost mid-day (UTC session key rollover)

- **Symptom:** Remy "forgets" everything from the morning's conversation around 11am AEDT. Each new message after that time is handled as if starting a fresh session with no prior context.
- **Impact:** High — conversational continuity is completely broken for half of each working day. Remy can't reference anything discussed before the UTC midnight boundary.
- **Root cause:** `SessionManager.get_session_key()` in `remy/bot/session.py` used `datetime.now(timezone.utc)` to generate the date component of the session filename (e.g. `user_8138498165_20260301.jsonl`). For a user in AEDT (UTC+11), UTC midnight falls at 11am local time. After 11am, the session key rolls to the next UTC date, but no JSONL file exists for that date yet — so `get_recent_turns()` returns an empty list and Remy starts with a blank context.
- **Priority:** High
- **Status:** ✅ Fixed
- **Fix:** `get_session_key()` now reads `settings.scheduler_timezone` and uses `zoneinfo.ZoneInfo` to get the user's local date. Session files now roll over at local midnight (AEST/AEDT) rather than UTC midnight. Existing UTC-dated session files are unaffected — they remain on disk and are accessible via `get_all_sessions()`.
- **Reported:** 2026-03-01
