# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`),
> Canvas multi-turn confirm + tool-loop fixes J1–J3 (`various`),
> Google Drive integration + file tool loop K1–K10 (`65624d0`, `1a16c84`, `436554a`, `5b29500`, `9d4876b`). All fixed.

---

## L — Drive Follow-up Read Failure (2026-06-14) — SUPERSEDED by §M

> Reframed 2026-06-14 after root-cause verification. L1/L2 are real but are *symptoms* of a
> deeper memory-poisoning bug (§M). They are folded into the §M plan (HANDOFF.md). Do not fix
> in isolation — patching the tool path alone leaves the stale-memory path feeding bad data
> (this is the "goose chase": K1–K10, L1, L2 all patched plumbing while memory replayed snapshots).

**L1** `[x]` **Drive tools not injected on follow-up turns** — fixed via §M Fix 2 (Redis session cache)
`_needs_drive_tools()` returns False for follow-ups (no Drive keyword) → `drive_tools=[]` → model
has no `drive_read_file` → "I don't have access to your Google Drive."
- §M Fix 2: inject tools when a Redis `drive_listing:{conversation_id}` cache exists (session-active),
  not by scanning history. No dependence on the model echoing IDs.

**L2** `[x]` **File IDs absent from history** — fixed via §M Fix 2 (server-side name→id cache)
Turn-1 reply lists names, no IDs (IDs lived only in the ephemeral tool result). Turn 2 can't call
`drive_read_file`.
- NOTE: the post-listing stop instruction L2 wanted to "add" ALREADY EXISTS (`stream.py:364–373`);
  it just omits IDs. L2 was written from a stale read of the file.
- `File` has NO Drive-id column and synced files don't exist → name→id can't come from the DB.
- §M Fix 2: server-side cache `{name→id}` from the listing call resolves IDs structurally.

---

## M — Drive Stale Content (root cause) (2026-06-14)

**Verified against live code + DB. This is the disease; §L are symptoms.**

**M1** `[x]` **Live Drive reads poison persistent memory → RAG/graph/summaries replay stale snapshots**
When the AI reads a Drive file via `drive_read_file`, its reply quotes that content. On every turn
(`api/chat/stream.py` ~L266–286) the reply is captured into FOUR memory layers with no freshness
awareness. The Drive file changes; the captured snapshots do not. Later turns retrieve the OLD
content as `[RELEVANT CONTEXT FROM EARLIER]` / graph facts / summary, and the model answers from it.
No tool-loop patch can fix a snapshot living in memory.

Leak points (severity ranked):
- `_graph_extract(user_id, req.message, full_response)` → Neo4j, **FULL response** — HIGHEST. 275 entities live.
- `update_memory` / `update_project_summary` / `compress_history` → memory sheet + summaries (full content).
- `_embed_exchange(...)` → pgvector, capped `user[:300]+assistant[:400]` — lower severity than first assumed.

- Fix (§M, HANDOFF): on Drive-read turns, write a REFERENCE (`name + id`, "fetched live, not cached")
  to memory instead of the body. Invariant: **live tools = only source of Drive CONTENT; memory holds
  REFERENCES, never stale BODIES.**
- Files: `backend/llm/service/stream.py`, `backend/api/chat/stream.py`, `backend/llm/graph_memory.py`

**M2** `[x]` **Muddy keyword gating cross-fires**
`_needs_drive_tools` shares `"google"` with `_needs_web_search` and `"document(s)"` with
`_needs_file_tools`. Generic tokens trigger the wrong toolset.
- Fix: require Drive-specific token (`drive/gdrive/sheet/slides/folder/gdoc`) or active session.
- Files: `backend/llm/service/context.py`

**M3** `[x]` **Global file fallback force-feeds ALL ready files into every chat** (latent)
`helpers.py:241–249` injects every `upload_status="ready"` file when none attached. Harmless now
(`ready_files=0`) but the first uploaded file then leaks into unrelated Drive chats too.
- Fix: scope to file-intent turns.
- Files: `backend/api/chat/helpers.py`

**M4** `[x]` **Stale docs misled the patch history** — `backend/CLAUDE.md` L189 corrected by root
`backend/CLAUDE.md` describes `sync_external_source_job` as calling `iter_chunks()`/`save_text()`/
enqueuing `process_file_job`. Verified FALSE: `iter_chunks` is never called; the job only refreshes
OAuth + sets `last_sync_at`. The stale doc is why HANDOFF authors kept assuming a live sync path.
- Fix: correct the doc (root-owned — `needs-root`).

**M5** `[x]` **No Drive/integration tests** — added `backend/tests/test_drive.py` (10 tests, mocked,
  no live API): keyword gating, listing→cache, name→id resolution, direct-id pass-through,
  search→cache, no-connection. All green.
- Followup (minor, non-blocking): one test (`test_drive_read_file_resolves_name_from_cache`) emits a
  RuntimeWarning from an un-awaited AsyncMock in the fixture — production code awaits correctly; tidy the mock.

---
