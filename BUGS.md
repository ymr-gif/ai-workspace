# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`). All fixed.

---

## Fixed — Creation confirm stuck across multi-turn (2026-06-05)

### J3 · [x] create_conversation never confirms when the reply arrives several turns after the ask

- **Symptom:** user asked "make a new session", got the confirmation ask, then over several turns re-asked / gave the title twice / said "yes" — every `create_conversation` rejected with "The user hasn't confirmed yet." No session created, so nothing rendered on the canvas (chatlog ~06:55–06:56). The model eventually narrated the tool call as raw JSON text out of confusion.

- **Root cause:** Layer 3 (`_user_replied_after_ask`) located the ask by scanning only the **last 4 messages** for the literal assistant string `"I need your confirmation"`. When confirmation arrived several turns later, the original ask had **scrolled out** of that window and the model's re-asks said "Please confirm"/"provide a title" (not the literal string) → `found_ask` never became True → permanent rejection while the Redis flow state sat at `pending` (300s TTL).

- **Fix:** the `pending` flow state already proves we asked (and `ask_user` ends that turn), so the **latest user message is necessarily the post-ask reply**. Replaced the window scan with `_user_confirmed_latest(db, conv_id)` — checks the latest user message directly: non-empty + non-negation + non-question (or explicit affirmative) ⇒ confirm. Robust to multi-turn delay; `?`-ending replies stay pending.

- **Verification:** live (70B, global) reproduced the exact 5-turn sequence → session created once at the title turn (`fdf2584a…` "TEST"), canvas session node auto-wired (`kind=user`), no duplicates; `?`-ending re-ask correctly stayed pending. New tests `tests/canvas/test_creation_guard_confirm.py` (5) lock Layer 3 — the guard had **zero** test coverage before, which is why it regressed twice (J1 follow-up, then J3). 71/71 canvas+retrieval.

---

## Fixed — Canvas tool robustness J2 (2026-06-05)

### J2 · [x] Bulk-delete loop-guard false trips + query_canvas brittleness + lost aborted turns

- **Symptom:** "delete all sessions excluding the global" aborted. Log trace: model wrote a `query_canvas` Cypher missing `{user_id: $uid}` → rejected → retried the *identical* broken query → loop-guard aborted; same turn it tried to delete the protected `input` + `global` nodes (core protection blocked them). The aborted turn rolled back — user message + work vanished from history.

- **Root cause:** guard + core-protection were healthy; the weaknesses were upstream — `query_canvas` requires hand-written scoped Cypher the 70B keeps botching, the model targeted protected nodes, and the abort path persisted nothing.

- **Fix (A+B+C+D, all verified live, 70B global):**

  | # | Change | File |
  |---|--------|------|
  | **A** | `get_canvas_graph` promoted to the PRIMARY inspection tool; `query_canvas` demoted to "advanced/optional". RULES tell the model to use `get_canvas_graph` to list. Live: "list every session" → one `get_canvas_graph`, answered, no loop. | `llm/tools/schemas.py`, `api/chat/stream.py` |
  | **B** | `query_canvas` auto-scopes the common omission: injects `{user_id: $uid}` into **every** bare `(var:CanvasNode)` pattern (`_BARE_CANVAS_NODE_RE`, no count limit), then **rejects** any `:CanvasNode` binding not scoped to `{user_id: $uid}` (`_UNSCOPED_CANVAS_RE`). | `agent/canvas_graph.py` |
  | **B-sec** | **Cross-tenant fix (security-review HIGH).** First cut auto-scoped only the *first* bare pattern (`count=1`) and skipped validation when `$uid` was anywhere in the query — so `MATCH (a:CanvasNode),(b:CanvasNode)` left `b` reading all tenants, and `WHERE n.user_id <> $uid` / literal `{user_id: 999}` slipped through. Now: scope all bindings + enforce every `:CanvasNode` carries `{user_id: $uid}` (pattern-map scoping is authoritative; a WHERE can't widen it). Tests cover multi-binding, partial, literal-foreign-id, and hostile-WHERE. | `agent/canvas_graph.py` |
  | **B+** | **Pre-existing bug found via new test:** the write-keyword guard uppercased the first word but compared against a lowercase set → *never matched*, so `query_canvas` (meant read-only) would run `DELETE`/`SET`. Replaced with a word-boundary, case-insensitive scan over the whole query (`_WRITE_RE`) — also catches `MATCH (...) DELETE n`. | `agent/canvas_graph.py` |
  | **C** | Deleting a protected node now returns a benign non-`Error:` "Skipped {id}: permanent infrastructure…" result so the model moves on instead of retrying. RULE added to skip `[CORE · protected]`/`[GLOBAL]` in bulk deletes. Live: "delete input + global" → 2 skip results, model explains, no loop. | `llm/tools/executor.py`, `api/chat/stream.py` |
  | **D** | Aborted/failed turns persist the user message + a short `⚠️ Turn aborted: <reason>` assistant note (commits the otherwise-rolled-back user msg). Live-confirmed: an aborted turn left both rows in history. | `api/chat/stream.py` |
  | **Guard refinement** | The signature loop-guard (J1 follow-up) false-tripped on parameterless `get_canvas_graph` (every call has identical args). Read-only tools now get `_MAX_IDENTICAL_READS=8`; write tools stay `_MAX_IDENTICAL_CALLS=3`. | `llm/service/stream.py` |

- **Verification:** `pytest tests/canvas tests/retrieval` 60/60 (incl. 9 new `query_canvas` scope/write-guard tests). Live (70B, global): bulk delete of 2 user sessions → both deleted, global excluded, no loop; protected delete → benign skip; benign `hello?` clean; creation flow (TestAlpha/TestBeta) intact.

---

## Fixed — Google Drive integration pipeline (2026-06-13)

### K1 · [x] Google Drive 401 loop — missing `prompt=consent` in OAuth URL

- **Symptom:** Every sync attempt sets `needs_reauth`. Re-authenticating fixes it for ~1 hour then loops again.
- **Root cause:** Google only returns `refresh_token` on first auth OR when `prompt=consent` is in the URL. Without it, re-auth returns only `access_token` → expires in 1h → no way to refresh → 401.
- **Fix:** Added `&prompt=consent` to `get_auth_url()` in `services/integrations/google_drive.py`. (`65624d0`)

### K2 · [x] Sync job proceeds with guaranteed-stale token when no refresh_token

- **Symptom:** Sync job calls Drive API with expired token, wastes a round-trip, gets 401.
- **Root cause:** When `expires_at < now` and `refresh_token is None`, `refresh_tokens()` returned unchanged expired credentials silently.
- **Fix:** Added early-exit guard in `sync_external_source_job` — fast-fails to `needs_reauth` when expired + no refresh_token. (`65624d0`)

### K3 · [x] `process_file_job` never fired after sync

- **Symptom:** Files created in DB after sync but never chunked/embedded — `upload_status` stuck at `uploaded`.
- **Root cause:** `asyncio.create_task(process_file_async(...))` used in ARQ worker. `get_arq_pool()` returns `None` in worker process → tasks abandoned silently.
- **Fix:** Replaced with `await ctx["redis"].enqueue_job("process_file_job", ...)`. (`1a16c84`)

### K4 · [x] `[embeddings] HTTP client not initialized` in ARQ worker

- **Symptom:** Embedding calls fail in worker process with "HTTP client not initialized".
- **Root cause:** `llm.client.client` (global `httpx.AsyncClient`) initialized in `main.py` lifespan only — ARQ worker is a separate process with no lifespan hook.
- **Fix:** Added `on_startup`/`on_shutdown` to `WorkerSettings` in `arq_worker.py`. (`1a16c84`)

### K5 · [x] File search always empty — `row.file_id` KeyError

- **Symptom:** `_search_files` in `api/search.py` always returns empty. Log: `_search_files failed: file_id`.
- **Root cause:** `select(FileChunk.id, FileModel.id, ...)` — both columns named `id` in result row, `row.file_id` doesn't exist.
- **Fix:** `FileModel.id.label("file_id")`. (`1a16c84`)

### K6 · [x] Drive-synced files not searchable in chat — embed_task gated

- **Symptom:** Chat RAG returns `provenance: 0 sources` even with Drive files synced and ready.
- **Root cause (A):** `embed_task` only created when `req.conversation_id or is_ref or req.file_ids` — fresh chats with no conversation_id never embedded the query.
- **Root cause (B):** No global file fallback — RAG only searched conversation-attached files, never all user's ready files.
- **Fix:** Always create `embed_task`; added global file fallback in `helpers.py` querying all user's `ready` files when none attached. (`1a16c84`)

---

## Fixed — File tool loop bugs (2026-06-13)

### K7 · [x] `search_in_file` / `search_across_files` crash with TypeError

- **Symptom:** Tool call returns `Error: sequence item 0: expected str instance, dict found`.
- **Root cause:** `retrieve_from_files()` returns `list[dict]`. Both functions passed raw list to `str.join()`.
- **Fix:** `"\n\n---\n\n".join(c["content"] for c in chunks)`. (`436554a`)

### K8 · [x] `list_files` returns "No files attached" when global fallback files exist

- **Symptom:** Agent sees file tools injected (global fallback found files) but `list_files` returns "No files attached to this conversation" → agent loops.
- **Root cause:** `_list_files` and `_search_across_files` only queried `ConversationFile` (conversation-attached), not the global fallback scope used by helpers.py.
- **Fix:** Added `user_id` param + fallback to all user's `ready` files when `ConversationFile` is empty. (`436554a`)

### K9 · [x] Agent retries identical `search_in_file` calls — no result count hint

- **Symptom:** `search_in_file` returns 1 chunk; agent calls it again with same args 3+ more times → loop guard fires.
- **Root cause:** No indication of whether 1 chunk is the complete result or partial — agent retried hoping for more.
- **Fix:** Appended `[N chunk(s) matched. Use read_file for full file content.]` to search responses. (`5b29500`)

### K10 · [x] Agent re-lists files repeatedly — `list_files` has no args so loop guard always fires at 4th call

- **Symptom:** `list_files called 4 times with identical args, aborting` — agent re-lists after every read/search cycle.
- **Root cause:** No completeness signal — agent treats `list_files` as a "reset" when confused.
- **Fix:** Appended `[N file(s) total. This list is complete — use search_in_file or read_file to access content.]` to response. (`9d4876b`)

---

## Fixed — Tool-loop errors + false creation framing (2026-06-04)

### J1 · [x] Model calls canvas tools repeatedly on benign messages, hits tool-loop abort

- **Symptom:** 70B reasoning model produced tool-loop errors on *benign* messages ("hello how are you", "suggest a new topic", "interesting topic?") — calling `create_conversation` / `get_canvas_graph` / `create_canvas_node` until the >3-same-tool abort or the 20-iteration `MAX_TOOL_ITERATIONS` cap. Visible to the user as "Tool loop detected".

- **Actual root cause (verified live, not what we first thought):** The model treats **every** turn in the JARVIS session as a canvas task and will spin on *whatever* canvas tool is offered. Prompt priming (naming `create_conversation`, the CONFIRMATION/SESSION blocks) was a *contributor*, not the cause — removing all of it did **not** stop the loop. Live proof:
  - Removed all creation priming + hardened rejection strings → model still called `create_conversation` 4× → abort. (cause 5, "learned/contaminated behavior", was the real driver.)
  - Gated `create_conversation` only → model switched to `create_canvas_node`/`wire_nodes` and looped on those.
  - Gated all canvas *write* tools, leaving read-only → model spun on `get_canvas_graph`/`query_canvas` ×20 → "Tool loop limit reached", 0 text.
  - **Only** withholding *all* canvas tools on benign turns made it answer in plain text.

- **Fix (live, verified):**

  | Change | File |
  |--------|------|
  | **`canvas_context_active(message, conv_id)`** — canvas tools offered only when the message names a canvas object (`_CANVAS_INTENT_RE`: canvas/node/session/conversation/wire/graph…) OR a creation flow is mid-confirmation (Redis state set) | `llm/tools/executor.py` |
  | Service layer drops **all** canvas tools when `canvas_context_active` is false — if none are offered, the model can't loop and must answer in text | `llm/service/stream.py` |
  | **Layer 3 confirm-turn regression fix** — the uncommitted "stale cross-check" had gated the `pending_specs` branch on re-detecting creation intent in the *latest* message; the confirm turn's message is "yes" (no intent) so it cleared the flow and rejected → creation could never complete. Reverted to gate on `_user_replied_after_ask` (affirmative reply after the ask). Canvas tool gating now covers the stale-leak case the cross-check was trying to handle. | `llm/tools/executor.py` |
  | Anti-priming cleanup (kept, defense-in-depth): RULES no longer name `create_conversation`; `create_conversation` schema drops the wrong manual create+wire procedure (auto-wiring owns it); `create_canvas_node` schema lists session as managed; rejection strings tell the model to stop retrying | `api/chat/stream.py`, `llm/tools/schemas.py`, `llm/tools/executor.py` |

- **Follow-up fix (2026-06-05) — confirm-turn looped on a bare title:** the ask says "provide a title", but Layer 3 (`_user_replied_after_ask`) required a `_CONFIRMATION_RE` yes-word. A user replying with a plain title ("ProjectPhoenix") never matched → reject → model retried → abort. (The earlier verify passed only because "yes, please create it" happened to match.) Fixed: after the ask, any non-empty, non-negation, non-question reply counts as confirmation (the title *is* the confirmation); `?`-ending replies stay pending so unrelated questions don't auto-confirm. Verified live: "can you make a new session?" → "ProjectPhoenix" creates once (10→11), no loop.

- **Verification (live, 70B forced, JARVIS session):**
  - Benign: "hello how are you" / "suggest a new topic" / "interesting topic?" → **0 tool calls**, real text answers, no loop.
  - Creation: "create a new session called Demo" → ask_user confirmation (flow=pending_specs) → "yes, please create it" → creates **exactly once** (conversations 9→10, "Demo"), session canvas node auto-created (`kind=user`) + wired, flow state cleared, model confirms in text.
  - Read intent: "what is on my canvas?" → `get_canvas_graph` offered + answered, no loop.
  - `pytest tests/retrieval/` 26/26 pass.

- **Ruled out:** `_CREATION_RE` catch-all (suspect 4) — gated behind a "session"/"conversation" token; "new topic"/"a story"/"hello" return no creation intent. Governs the guard's verdict, not whether the model calls the tool.

- **Residual fix (2026-06-05) — all canvas injection now intent-gated:** a single `canvas_active = canvas_context_active(message, conv_id)` flag in `api/chat/stream.py` now gates *every* canvas-flavored prompt block on benign turns: the boot `> CANVAS:` line (`format_boot_log(report, include_canvas=canvas_active)` in `agent/boot.py`), `last_session`, node inventory, and `[CANVAS STATE]`. Model-health + scratchpad boot lines are kept (not canvas). Verified live (70B): "hello?" / "how are you?" → clean text, **no canvas narration, 0 tools**; "how many nodes on my canvas?" → `get_canvas_graph` → "You have 8 nodes." Old node-ID echoes ("the No name session a644dbbd…") came from the JARVIS session's own *conversation history* (176 dev/test turns, 2026-06-01→05), not a fresh injection — backed up to `backend/storage/backups/jarvis_msgs_*.csv` and pending a history clear.

