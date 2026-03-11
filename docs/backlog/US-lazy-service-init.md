# User Story: Lazy Service Initialisation

**Status:** ⬜ Backlog

## Summary
As a user, I want Remy to start up quickly so that the bot is responsive within seconds
of launch, rather than waiting ~15s for all integrations to initialise eagerly.

---

## Background

`main.py` currently constructs all services at startup unconditionally: Google Workspace
clients, `FileIndexer` (which starts 4 background tasks), voice transcriber, and the
embedding model. Many of these are only needed when specific tools are invoked — for
example, the voice transcriber is only needed when an audio message arrives.

Identified in Phase 5 item 16 of `docs/archive/consolidation-review-2026-03.md`. Also
noted: `FileIndexer` starts 4 background tasks at startup, contributing significantly to
cold-start time and memory pressure before any user interaction.

---

## Acceptance Criteria

1. **Bot is accepting Telegram messages within 3s of `make run`** (currently ~15s).
2. **Google Workspace clients initialise on first use**, not at startup. The first
   request that needs Gmail/Calendar/Contacts/Docs pays the init cost; subsequent
   requests use the cached client.
3. **`FileIndexer` starts lazily** — indexing background tasks begin only when a file
   tool is first invoked, not during `main.py` startup.
4. **Voice transcriber loads on first audio message**, not at startup.
5. **Embedding model loads on first similarity search**, not at startup.
6. **Startup log clearly shows "ready" before any lazy-init services have loaded.**
7. **No functional regression** — all tools still work correctly after lazy init;
   first-use latency is acceptable (no timeout errors).

---

## Implementation

**Files:** `remy/main.py`, `remy/startup_context.py`, `remy/google/` (client files),
`remy/memory/file_index.py`, `remy/voice/` (transcriber), `remy/memory/embeddings.py`

### Pattern: lazy singleton via property

```python
class StartupContext:
    _gmail_client: GmailClient | None = None

    @property
    def gmail_client(self) -> GmailClient:
        if self._gmail_client is None:
            self._gmail_client = GmailClient(credentials=self.google_creds)
        return self._gmail_client
```

### Pattern: FileIndexer deferred start

```python
# In main.py — instead of:
await file_indexer.start()  # starts 4 tasks immediately

# Do:
# file_indexer.start() is called inside the first tool invocation that needs it
```

### Notes

- Google OAuth credential loading (reading token file from disk) should still happen at
  startup — it's fast. The slow part is the first API call, which can be lazy.
- The embedding model (`sentence-transformers`) is the largest single startup cost; it
  loads a ~90MB model. Deferring this alone likely halves cold-start time.
- Thread safety: lazy init in async code should use `asyncio.Lock` to prevent double-init
  under concurrent first-use.

---

## Test Cases

| Scenario | Expected |
|---|---|
| Cold start | Log shows "ready" in < 3s |
| First `/gmail-unread` (or equivalent tool call) | GmailClient initialises; request succeeds |
| Second Gmail request | No re-init; uses cached client |
| First audio message | Voice transcriber loads; transcription succeeds |
| File tool invoked | FileIndexer starts; subsequent file ops work |
| Two concurrent first-use requests | No double-init; asyncio.Lock prevents race |

---

## Out of Scope

- Changing the Google OAuth flow itself
- Reducing the number of background tasks `FileIndexer` runs (separate refactor)
- `ProactiveScheduler` dependency reduction (consolidation-review Phase 5 item 17)
