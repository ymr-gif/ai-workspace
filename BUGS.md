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

**M6** `[x]` **Follow-up "read X" re-listed instead of reading** — found by live freshness check, fixed
The L1/L2 plumbing worked (tools injected on follow-up, server-side name→id resolver present) but the
model never reached the read path: `drive_read_file`'s schema said `file_id` must be "the ID from
drive_list_files", so on a follow-up turn the model re-called `drive_list_files` to obtain an ID
instead of reading. The name→id resolver was invisible to the model.
- Fix: `schemas.py` — advertise that `drive_read_file` accepts the exact file NAME from a prior
  listing (system resolves it); `stream.py` injected rules — add "name a file → call drive_read_file
  directly with the name; do not re-list".
- Verified live: turn 2 "read JARVIS Test Note" (no Drive keyword) → single `drive_read_file`,
  `drive_read=True`, fresh body returned; pgvector stored only a reference, not the body.
- Files: `backend/llm/tools/schemas.py`, `backend/llm/service/stream.py`

---

## N — Drive listing dumped on non-Drive turns (2026-06-14) — regression from M-series Fix 2

**N1** `[x]` **Full Drive file listing returned in response to unrelated messages** — fixed + verified live
(A2 "stale memory with 6 symptoms" in a cache-active conv → no tools, no dump; B1 incidental "drive"
mention → no listing; A3 follow-up "read X" → drive_read_file still works)
Reproduced in live JARVIS chat: messages with no Drive request ("the issue is backend, stale memory
with 6 symptoms"; pasted BUGS.md M1 text) caused the model to dump the entire 60-file Drive listing.

Two confirmed triggers:
- **Cache-active over-injection (regression from §M Fix 2):** Drive tools are injected whenever
  `drive_listing:{conversation_id}` exists in Redis. That cache has a 3600s TTL, so for ~1h after one
  listing, EVERY message in the conversation gets the full Drive toolset (incl. `drive_list_files`).
  The 70B, with the list tool available + history saturated with prior listings, re-lists compulsively.
  Verified: `_needs_drive_tools("the issue is backend...")=False`, yet listing still dumped → cache path.
- **Keyword fires on incidental mentions:** `_needs_drive_tools("M1 Live Drive reads poison memory")=True`
  — the bare word "drive" anywhere triggers a listing even when the user is *discussing* Drive, not
  requesting files.
- Compounding: 60-file listings persist verbatim as assistant messages → poison history → bias to re-list.

Fix (planned, HANDOFF — scope 1–3):
- Cache-active path injects ONLY `drive_read_file` (not list/search) — cache exists ⇒ listing already
  happened ⇒ follow-up is a read, never a re-list.
- Gate cache-active read tool behind read-intent (`_wants_drive_read`).
- Tighten `_needs_drive_tools`: require Drive noun + action verb, not bare "drive".
- (deferred) de-poison history by persisting listings as a compact reference.
- Files: `backend/llm/service/stream.py`, `backend/llm/service/context.py`

---

## O — Memory hygiene epic (2026-06-14) — diagnosed from realtime JARVIS chat

Surfaced by the live JARVIS chat (off-by-one symptom recital, lost thread, canvas bleed). Verified
against DB/graph. Epic plan + safe-reset tooling in HANDOFF.md (delegated to backend). Evidence:
mega-conversation `c01258e8` = 9 days / 206 msgs / 335k tokens / 16 tool-loop aborts (72% of all
admin msgs); 816-char summary; sheet `[CORRECTIONS]` ~80% dead Canvas errors; duplicate Neo4j
entities (5 Xeon/P40 variants); `message_embeddings` global per user → cross-conversation bleed.

**O1** `[x]` **Sheet choked by dead-Canvas `[CORRECTIONS]`** (Canvas removed 2026-06-09; never purged)
→ crowds out current facts; compaction doesn't prune obsolete/removed-feature entries.
— Fixed by S1: `_prune_canvas_corrections()` (including inline-format bug fix 2026-06-14).
  Verified: memory sheet pruned 3460→2009 chars, 0 canvas terms remain.

**O2** `[x]` **Cross-conversation RAG bleed** — `message_embeddings` is global per user, no
conversation scoping/recency weighting → other threads' content recalled as if in this one.
— Fixed by S2: `retrieve_global()` filters `Conversation.is_archived == False`.
  Verified: 5 archived convs excluded from RAG pool.

**O3** `[x]` **Bulky tool outputs persisted verbatim** (Drive/file listings) → history poison
(formerly N1 deferred #4). Store a compact reference for history context.
— Fixed by S3: `compress_tool_dumps()` in `content_filter.py`, wired in `stream.py:256`.
  Verified: 10 unit tests pass; large code blocks (>20 lines) replaced with `[~s3~]` references.

**O4** `[x]` **Unbounded conversations + over-lossy summaries (highest impact)** — no rotation/length
cap; one thread accrues days of content; 816-char summary can't recover detail → context degrades
(off-by-one, lost thread, pre-emption).
— Fixed by S4: rotation thresholds (msgs>80 OR tokens>120k OR idle>3d); summary budget 200→500 words.
  Verified: `c01258e8` (206 msgs, 335k tokens) archived at reset; 5 convs rotated total.

**O5** `[x]` **Graph entity duplication** — case/format variants stored as distinct entities; needs
normalized MERGE + a dedup pass.
— Fixed by `merge_duplicate_entities()` called during soft reset + normal compaction.
  Verified: 33 Xeon/P40 variants merged to one each. 258 entities remain.

**O6** `[x]` **Safe Memory Reset / fresh start** (new tooling) — admin-only, backup-first, dry-run
default, reversible (`UserMemoryVersion` + export ZIP + graph dump); `soft` prune vs `hard` reset.
— Fixed by Phase 1: `POST /admin/memory/reset` endpoint; backup ZIP + graph dump written.
  Verified: dry-run returns report; soft reset archives+prunes+dedups; v67 snapshot preserved.
  Follow-up: `POST /admin/memory/restore` not implemented (manual restore via versions possible).

**O7** `[x]` **Soft-reset prune too narrow — leaves session/node/topic cruft + canvas graph entities** — fixed (60 tests green; live dry-run clean)
After `level=soft` "succeeded", the sheet `[CORRECTIONS]` still held session/node/topic/tool-loop
entries (prune only matched literal `canvas`/`session node`/`workspace node`/`output node`), 20+
canvas entities remained in Neo4j (soft reset dedups but never purges dead-feature entities), and the
Xeon spec stayed duplicated across 3 prefixed variants (normalizer can't merge prefixed names). Root
hand-cleaned user_id=1 (sheet 2010→806, graph 259→230). Durable fix delegated (HANDOFF): widen prune
terms, add graph canvas-purge to soft reset, merge substring/prefixed variants preserving rels.
- Files: `backend/llm/summarizer/compact.py`, admin memory-reset handler, `backend/llm/graph_memory.py`

---
