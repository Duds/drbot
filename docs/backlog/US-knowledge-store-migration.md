# User Story: Complete KnowledgeStore Migration

**Status:** ⬜ Backlog

## Summary
As a developer, I want `FactStore` and `GoalStore` write paths retired so that all memory
data flows through `KnowledgeStore` as the single source of truth, eliminating the
dual-store inconsistency.

---

## Background

`main.py` constructs all three stores. `ToolRegistry` and `make_handlers()` receive all
three. The comment in `main.py` acknowledges that `KnowledgeStore` supersedes the legacy
stores for new data, but both write paths remain active. This means facts and goals can be
silently written to two different stores with no guarantee of parity.

Identified in Phase 1 item 4 and Phase 4 item 14 of
`docs/archive/consolidation-review-2026-03.md`.

---

## Acceptance Criteria

1. **No new writes to `FactStore` or `GoalStore`.** All `add`/`update`/`delete` operations
   in tool handlers and extractors target `KnowledgeStore` only.
2. **Read compatibility maintained.** Anything that reads from `FactStore` or `GoalStore`
   either migrates to `KnowledgeStore` reads or is wrapped in a compatibility adapter that
   reads from `KnowledgeStore`.
3. **`main.py` no longer constructs `FactStore` or `GoalStore`** except as read adapters
   (if still needed).
4. **`make_handlers()` and `ToolRegistry` no longer accept `fact_store` / `goal_store`
   constructor parameters** (or they are deprecated and ignored).
5. **All existing tests pass.** No regressions in `test_proactive_memory.py`,
   `test_tool_registry.py`, or `test_handlers_file_project.py`.
6. **Existing DB rows in `facts` and `goals` tables are still readable** — migration does
   not drop or wipe legacy tables.

---

## Implementation

**Files:** `remy/main.py`, `remy/startup_context.py`, `remy/bot/handler_deps.py`,
`remy/ai/tools/registry.py`, `remy/ai/tools/context.py`, `remy/memory/facts.py`,
`remy/memory/goals.py`, `remy/memory/knowledge.py`, `tests/test_tool_registry.py`,
`tests/test_proactive_memory.py`

### Approach

1. Audit every call site that writes to `FactStore` or `GoalStore`. Convert each to a
   `KnowledgeStore.add_item()` call with appropriate `entity_type` (`"fact"` or `"goal"`)
   and `metadata`.

2. For read-only callers (e.g. memory injector, `/goals` display) that still read from
   `FactStore`/`GoalStore`, either:
   - Update them to query `KnowledgeStore` by `entity_type`, or
   - Leave `FactStore`/`GoalStore` as thin read adapters backed by `KnowledgeStore` during
     a transitional period.

3. Remove `fact_store` and `goal_store` from `ToolContext`, `ToolRegistry.__init__()`,
   `make_handlers()`, and `MemoryDeps`.

4. Update `main.py` to not instantiate `FactStore`/`GoalStore` for write purposes.

5. Update all affected tests.

```python
# Before (legacy write)
await fact_store.add_fact(user_id, content, metadata)

# After (unified write)
await knowledge_store.add_item(user_id, "fact", content, metadata)
```

### Notes

- Check `remy/memory/injector.py` — it reads from multiple stores to build the `<memory>`
  block. This will need updating to query `KnowledgeStore` by entity type.
- `GoalStore` may have its own schema columns (e.g. `status`, `priority`). Map these to
  `KnowledgeStore.metadata`.
- Do **not** drop `facts` / `goals` tables from the DB schema — backwards compatibility
  with existing databases.

---

## Test Cases

| Scenario | Expected |
|---|---|
| `manage_memory add` tool call | Fact stored in `knowledge` table, not `facts` table |
| Memory injector builds context block | Reads from `knowledge` table correctly |
| `/goals` command | Goals retrieved from `knowledge` table by `entity_type='goal'` |
| Existing DB with rows in `facts` table | Rows still readable; no crash |
| `ToolContext` constructed without `fact_store` | No error |

---

## Out of Scope

- Dropping `FactStore` or `GoalStore` classes entirely (leave for a later cleanup)
- DB table migration / backfill of legacy rows into `knowledge` table
- Changes to `KnowledgeStore` schema itself
