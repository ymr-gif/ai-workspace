# HANDOFF
- Updated: 2026-06-28
- Status: **Q3 Task B DONE — SHIPPED + verified live (root direct, override).** Session-latched semantic Drive gate. Cold "ehllo" over-fire now **structurally impossible** (schema absent pre-latch). Ready for root close-out.
- Owner: root (close-out).

> **graphify-first mandate applies.** Before reading/grepping any source file, run `graphify query "<q>"`
> / `graphify explain` / `graphify path`. Raw reads only to orient-then-edit specific lines. After code: `graphify update .`.

---

## Recently shipped (full detail in History + `backend/tests/VERIFICATION_LAUNCH.md`)

**Verification tiers + launch runbook + CI** — built and **run live** against the running stack:
- `backend/pytest.ini` + `backend/tests/conftest.py` — 4 markers (`unit`/`infra`/`live_nim`/`optional`),
  auto-skip gating, shared HTTP fixtures. Existing 175 + 26 retrieval stay green; plain `pytest`
  skips the 58 opt-in tests on a laptop.
- `backend/tests/live/` — HTTP-driven E2E (real NIM/DB/Redis/Neo4j): chat SSE + `done` contract,
  grounding persistence, non-stream + model override + cache-bypass, **RAG tool loop**, files
  CRUD/dedup, endpoint sweep, admin + secret masking, auth lifecycle, health/metrics/401.
  **42 passed / 3 skipped** (voice / push off; web search since enabled — see next bullet).
- `backend/tests/live/test_tools_integrations.py` — **full tool + integration sweep**: every agent-tool
  family (web search, fetch_url, file ops, query_graph, ask_user, write_memory confirm) + Drive +
  Calendar through real NIM. **13 passed / 1 skipped** (only Gmail — not connected). Web search
  enabled (searxng) + verified; Calendar verified live after the Google Cloud API/scope fix.
- `backend/tests/integration/` — `infra` tier (migrations→047, pgvector `vector(1024)`, core tables,
  Redis NX lock, Neo4j `entity_name_ft`). Facts cross-checked directly against the live DBs.
- `backend/scripts/smoke.sh` — post-deploy smoke; **ran PASS** (70B reply, `cost=$0.000242`).
- `.github/workflows/ci.yml` — unit/retrieval/infra per-PR; live+smoke nightly/manual on a deployed URL.
- `backend/tests/VERIFICATION_LAUNCH.md` — master runbook + NIM-interim-prod launch checklist + rollback.

> Override note: user directed root to implement this directly (verification too high-stakes to risk
> worker misinterpretation). One-time, not a standing change. Docs appended to `backend/CLAUDE.md` +
> `docker/CLAUDE.md`; `graphify update .` run. No root-owned env files changed (test env vars are
> documented in `pytest.ini`/runbook, not `.env`).

---

## COMPLETED PHASE: Q3 Task B — Session-latched semantic Drive gate (SHIPPED 2026-06-28, root override)

> **graphify-first mandate.** Re-anchor every file/line below via `graphify query`/`explain` before
> editing — line numbers are a 2026-06-28 snapshot and drift. After code: `graphify update .`.

**Why:** Drive tools fire on trivial turns (`drive_list_files {}` on "ehllo"/"thanks"). Root cause is
structural — the capability gate injects Drive schemas whenever the connector is active, so the
tool-eager 70B calls them from the schema alone. Task A (abstention `_DRIVE_RULES` prompt text) shipped
+ measured **0/5 on test-4** — prompt steering had zero effect. Task B removes the Drive schema from
context until an embedding-cosine intent latch fires, making the cold "ehllo" case **structurally
impossible**. Task A's rules stay as the post-latch abstention layer (two windows, two mechanisms).

**Scope:** 4 files + 1 new module. Stay inside them. Do **not** touch routing, fallback chain, RAG
retrieval, `cache.py`, or `_DRIVE_RULES` content (Task A owns it — it covers post-latch). Adds **no**
new env vars.

**Build the eval set FIRST** — the threshold is unsettable without it.

### Tasks
- [x] **B0 — Eval set (do first).** Create `backend/tests/drive_intent_eval.jsonl` — **40 labeled
  turns**: 20 Drive-intent (varied phrasings, not clustered on one verb), 20 non-Drive (greetings/acks
  **and** substantive non-Drive questions). Sets the threshold AND is the reported gate-accuracy number.
- [x] **B1 — `backend/llm/tools/drive_intent.py`** (new; keep logic off the hot path). `_DRIVE_INTENT_PHRASES`
  (~15–20 example sentences) → centroid **derived at boot** (never a hardcoded vector); `get_centroid()`
  (warm cache), `drive_intent_score(query_emb) -> float` (cosine via normalized dot), `DRIVE_INTENT_THRESHOLD`
  (placeholder → set from B0). **Gotchas (confirmed live):** import is `from llm.embeddings import embed as
  embed_text` (`embed_text` is not a real export); `embed` is **async** — `_build_centroid` must
  `await asyncio.gather(*[embed(p, input_type="query") for p in phrases])`, not a sync list-comp;
  `input_type="query"` is **correct** (e5 asymmetric — do not switch to passage); `query_emb is None` →
  score 0.0 → not latched.
- [x] **B2 — Thread `query_emb`** (pure plumbing, no new embed). Add `query_emb=None` to `generate_stream`
  signature (`llm/service/stream.py:92`). Return `query_emb` from `_build_stream_context` (`api/chat/helpers.py`
  — currently local at L254, dropped after RAG). Pass it at the call site `api/chat/stream.py:271` alongside
  `retrieved_chunks`. Confirm the `None` path (`helpers.py:241` embeds unconditionally today).
- [x] **B3 — Redis latch + conditional schema injection.** Storage = `drive_latched:{conv_id}` string flag,
  mirroring `drive_listing:{conv_id}` at `stream.py:180–183`. **Read** beside `_drive_cache_active`
  (`if _drive_active and conv_id and USE_REDIS`): `exists(f"drive_latched:{conv_id}")`. **Flip — same turn,
  AFTER B2 threads `query_emb`, BEFORE `injected_tools` assembly (L221):** if not latched and
  `drive_intent_score(query_emb) >= DRIVE_INTENT_THRESHOLD` → `set(..., "1", ex=3600)` **and** set
  `_drive_latched=True` in-process (latch-then-serve). TTL 3600s, refreshed per latched turn. **USE_REDIS
  off:** same-turn score only (no stickiness); **do NOT** fall back to capability-only (reinstates the bug).
  Add `drive_latched: bool = False` to `ToolContext` (`context_types.py:20`), set from `_drive_latched` at
  the `ToolContext(...)` build (`stream.py:201`). Change effective `_drive_gate` (`drive_tools.py:56`) from
  `ctx.drive_active` to `ctx.drive_active and ctx.drive_latched` — pre-latch the schemas **and** `_DRIVE_RULES`
  drop automatically (rules ride `injected_tools` at `stream.py:280–287`). **Cache invariant:** latch flips
  **once** → one prefix-cache miss, then byte-stable; do not re-evaluate/reorder per turn; keep name-sort.
- [x] **Migration note** — write into `backend/CLAUDE.md` `LLM_BACKEND` invariant (and cross-post to
  `QUEUE.md` Q1 Recorded on close-out): centroid auto-regenerates at boot under bge, but `DRIVE_INTENT_THRESHOLD`
  is e5-tuned and wrong for bge — re-run the 40-example eval under bge + re-tune. Symptom if skipped: latch
  fires too early/late silently.
- [x] **Unit test** for `drive_intent_score` (centroid + None-path + dispatch, mocked `embed`).
- [x] Run `graphify update .`; fill `### Recorded`; `mv HANDOFF.md ../HANDOFF.md` for root close-out.

### Verification (run all)
1. **B0 accuracy first (early kill-signal — report before anything downstream).** Embed all 40 eval turns as
   `query`, score vs centroid, pick the threshold best-separating the 20/20. Record correct count + which miss.
   Heavy overlap → revise phrases before trusting the gate; report it, don't paper over.
2. **Behavioral** (stack up, `docker-api-1` healthy; rebuild after edits — code is baked, no bind-mount:
   `cd docker && docker compose -f docker-compose.yml up -d --build api`; admin Drive-active; ground-truth via
   `tool_call_logs`):

   | # | Input | Setup | Pass | Proves |
   |---|---|---|---|---|
   | 1 | `ehllo` | fresh | no call — **schema absent** (assert structurally) | pre-latch removal |
   | 2 | `hello?` | after #1, pre-latch | no call, schema still absent | no spurious flip |
   | 3 | real Drive request | triggers latch | flips, schema appears **same turn**, `drive_list_files` fires | same-turn serve |
   | 4 | `thanks` | right after #3 | no call (schema present — A's job) | A+B division |
   | 5 | another Drive request | later same session | fires, no cache-disrupting reassembly | latch stable |

   Test 1 = the structural guarantee: assert/log Drive schemas absent from the assembled tool list pre-latch,
   don't infer from behavior. This is the before/after vs Task A's 0/5. **Cleanup (pollution):** delete each
   test conversation + orphaned `tool_call_logs` (`conversation_id IS NULL AND created_at > now()-interval
   '15 min'`); verify admin memory clean.
3. **Regression:** `pytest tests/retrieval/test_hybrid_eval.py tests/test_drive.py tests/test_calendar.py -v`
   stays green.

### Recorded — SHIPPED 2026-06-28 (root direct, override)

**Files touched (5 + 1 new module + 1 new eval + 1 new test):**
- NEW `backend/llm/tools/drive_intent.py` — `_DRIVE_INTENT_PHRASES` (18, file-anchored), boot-derived
  normalized-mean centroid (`_build_centroid` embeds **sequentially with retry** → deterministic full
  18/18 set; partial → returns None + self-heals on next call), async `drive_intent_score(query_emb)`
  (cosine; None/empty/no-centroid → 0.0), `warm_centroid()`, `DRIVE_INTENT_THRESHOLD=0.60`.
- NEW `backend/tests/drive_intent_eval.jsonl` — 40 labeled turns (20 drive / 20 non-drive).
- NEW `backend/tests/test_drive_intent.py` — 7 unit tests (cosine math, None fail-safe, no-centroid
  fail-safe, query-encoded centroid mean, incomplete-set→None). All green.
- `llm/tools/context_types.py` — `ToolContext.drive_latched: bool = False`.
- `llm/tools/builtin/drive_tools.py` — `_drive_gate` → `ctx.drive_active AND ctx.drive_latched`; docstring updated.
- `llm/service/stream.py` — `query_emb` param added; `_drive_latched` read (Redis `drive_latched:{conv_id}`,
  beside `drive_listing`), **latch-then-serve flip** before `injected_tools` assembly (score ≥ threshold →
  `set ex=3600` + in-process flag), TTL refresh on already-latched turns, `drive_latched=_drive_latched`
  into `ToolContext`.
- `api/chat/helpers.py` — `_build_stream_context` return dict now carries `query_emb`.
- `api/chat/stream.py` — call site passes `query_emb=ctx.get("query_emb")`.
- `main.py` — lifespan warms the centroid after the embedding-model check (logs `centroid built 18/18`).
- Docs: `backend/CLAUDE.md` Drive-injection line rewritten + LLM_BACKEND bge re-tune migration note.

**Latch mechanism:** Redis `drive_latched:{conv_id}` string flag, `ex=3600`, refreshed per latched turn,
`USE_REDIS`-gated; off → same-turn score only (fail toward fewer tools, never capability-only). Sticky →
one prefix-cache miss on the flip turn, then byte-stable. No new embed call (reuses `query_emb`).

**B0 / threshold tuning (live nv-embedqa-e5-v5, 40-set, sequential embeds):** centroid built from the 18
file-anchored phrases. Score separation: **greetings/acks/chit-chat 0.29–0.39 vs file-requests — wide,
clean margin** (the actual over-fire bug; can never latch). Drive-intent vs *substantive task/coding*
imperatives **overlap intrinsically** (single-centroid cosine ceiling — "help me debug" 0.66, "summarize"
0.61 score as high as weak Drive asks). Accuracy-max threshold = 0.51 → 33/40 but 7 task-turn false
positives. **Chose 0.60 (precision-biased, per spec "fail toward fewer tools"): overall 32/40, recall
14/20, specificity 18/20.** A weakly-phrased Drive ask that misses just needs a rephrase; only
summarize/debug-style turns leak (then Task A's `_DRIVE_RULES` covers the post-latch call).

**Behavioral (live, admin Drive-active, ground-truthed vs `tool_call_logs` + Redis latch key):**
- **T1 `ehllo` (fresh): PASS — `latched=False`, schema ABSENT, no fire.** ⭐ The structural guarantee:
  latch key absent → `_drive_gate` False → Drive schema never assembled. **Before/after: Task A `ehllo`
  fired 0/5; Task B `ehllo` is structurally unable to fire.**
- **T2 `hello?`: PASS** — no spurious flip, still schema-absent.
- **T3 "what files do I have in my drive?": PASS** — latch flips + `drive_list_files` fires **same turn** (latch-then-serve).
- **T4 `thanks` (post-latch): LEAKED** — fired. **This is Task A's territory by design** (schema present
  post-latch; B doesn't protect it — spec-acknowledged). B did its part: `latched=True`, schema present.
  Matches Task A's known 0/5 on this case; now isolated to *post-latch* trivial turns only.
- **T5 "find my budget spreadsheet": PASS** — `drive_search` fired, latch stayed `1` (stable, no re-flip).
- **B's own guarantees: 4/4 (T1, T2, T3, T5).** Net: over-fire surface shrank from "every greeting/ack,
  cold or warm" → "only post-latch trivial turns after a genuine in-session Drive request."
- Test pollution cleaned (2 convs + 5 orphan tool-logs deleted; admin test-conv count = 0 verified).

**Regression:** `test_drive` (gate updated for latch), `test_drive_intent` (7), `test_calendar` (7),
`tests/retrieval` (26) all green on host. `graphify update .` run (2050 nodes).

**Known limitations / future hardening (all tracked in BUGS.md residual):**
- **T4 post-latch leak** — `thanks` after a listing still fires; documented case for hardening `_DRIVE_RULES`
  or an 8B pre-pass (Option C). NOT built (record-first per spec).
- **Session-poisoning via false latch** — the latch is sticky 1h, and task/coding imperatives
  ("help me debug" 0.66, "summarize" 0.61) overlap weak Drive asks (gate 32/40, single-centroid ceiling).
  So one false latch on a coding turn flips Drive on for the whole session → the T4 leak then applies to
  every following turn. Milder than the original bug (session-scoped, only after a wrong latch) but same
  family. Mitigations: raise threshold to 0.65–0.70, make the latch decay/non-sticky, or a 2-class/contrastive gate.
- **Verification rigor** — T1/T2 are structural/deterministic (firm). T3/T4/T5 are probabilistic 70B
  behavior, run **once each**, not the spec's 3–5 repeats — suggestive, not statistically settled.

---

## Pipeline

**Blocked / trigger-gated (nothing buildable-now):**
- **#22 Multi-Modal Memory** — trigger-gated (BUGS Q-D2). Build only on the trigger. *(roadmap "Q3" — NOT the `QUEUE.md` Q3 Drive fix above.)*
- **Outlook/CalDAV calendar, Gmail send/write** — deferred. Promote + spec if wanted.
- **Q1 Home-Server Port** → `QUEUE.md` Q1 (box-blocked: 2×P40).
- **#20 real ASR (Whisper)** → `QUEUE.md` Q2 (box-blocked; STT stub ships).

To resume: promote one of the above (root specs via `AskUserQuestion` → writes a phase → delegates).

---

## HANDOFF Protocol — Quick Reference

- **One HANDOFF.md only.** This is it. To pass on, edit in place then `mv` — never `Write` a second copy.
- **Sequenced:** do only the active phase; `mv` to the next owner when done; tick your own boxes before `mv`.
- **Root** plans/delegates; does not implement (except trivial root-file tweaks or explicit user override). Workers implement their own dir only.
- **Root-owned files** (workers must not edit): `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md` `QUEUE.md`. Cross-dir/root need → set `status: needs-root`, pass back.

> Full protocol: `../HANDOFF_PROTOCOL.md`

---

## History
| Date       | Feature                                  | Notes |
|------------|------------------------------------------|-------|
| 2026-06-28 | **Q3 Task B — session-latched semantic Drive gate SHIPPED + verified live** (root direct, override) | User overrode the HANDOFF protocol → root implemented all of Task B. New `llm/tools/drive_intent.py` (boot-derived e5 centroid from 18 file-anchored phrases, deterministic retry build, async cosine score, `DRIVE_INTENT_THRESHOLD=0.60`); `query_emb` threaded helpers→stream; Redis `drive_latched:{conv_id}` latch (latch-then-serve same turn, sticky, TTL 3600, `USE_REDIS`-gated); `_drive_gate` → `drive_active AND drive_latched`; `ToolContext.drive_latched`; centroid warmed in lifespan. **Live behavioral: T1 `ehllo` structurally schema-absent (no fire) — was 0/5 under Task A; T2 pass; T3 latch-flips-and-fires same turn; T5 latch-stable fires; T4 `thanks` leaks = Task A's post-latch territory, by design.** B's guarantees 4/4. Threshold tuned vs 40-set live (greetings clean-separated 0.29–0.39; task-imperatives overlap = single-centroid ceiling, chose precision-biased 0.60 → 32/40, recall 14/20, spec 18/20). Unit 7✓, regression (drive/calendar/retrieval) green; pollution cleaned; `graphify update .`; bge re-tune migration note in `backend/CLAUDE.md`. Bug (BUGS.md "Drive fires on greetings") → cold case closed; post-latch trivial-turn leak remains (Option C deferred, record-first). |
| 2026-06-28 | **Q3 Task B promoted → backend** (root) | Task A's test-4 = 0/5 fired Task B's mandatory trigger. Root promoted the session-latched semantic Drive gate from `QUEUE.md` Q3 into this file as the active backend phase (B0 eval-set-first, B1 `drive_intent.py` centroid, B2 `query_emb` threading, B3 Redis `drive_latched:{conv_id}` latch + gate flip), deleted the Q3 Task B block from `QUEUE.md`, `mv`'d HANDOFF to `backend/`. Anchors re-verified via graphify (lines drifted from snapshot). Plan: `~/.claude/plans/read-queue-md-and-plan-cheeky-pancake.md`. |
| 2026-06-28 | **Q3 Task A — abstention-biased Drive rules SHIPPED + measured ineffective** (root direct, override) | Rewrote `_DRIVE_RULES` (`backend/llm/tools/builtin/drive_tools.py`, one symbol — `_POST_LISTING`/`_drive_gate`/registrations untouched) to abstention-biased text; rebuilt api image; `graphify update .`. Live behavioral battery (admin, Drive-active, 5 trials/test, ground-truthed vs `tool_call_logs`): **T1 `ehllo` 0/5 no-fire · T2 `hello?` 0/5 · T3 real request 5/5 fires (correct) · T4 `thanks` 0/5** — `drive_list_files {}` fired on every greeting/ack turn, zero reduction. Confirms the schema (not the prompt) is causal. **Task B now mandatory** (was conditional on test-4 rate). Test convs + orphan tool-logs cleaned up; admin user-memory verified clean. Bug stays open. Docs: `BUGS.md`, `QUEUE.md` Q3, this file. |
| 2026-06-22 | **Calendar fully working — verified live** (root direct, override) | User enabled Calendar API + `calendar.events` scope in Google Cloud + reconnected the connector. Calendar now returns real events; `test_calendar_list_events` + `test_calendar_create_confirm_sentinel` **pass** (sweep now **13✓/1 skip**, only gmail skips). The 403 hardening + loop-guard graceful-reply fix stay as defense. Docs/memory marked resolved. |
| 2026-06-22 | **Calendar 403 UX fix — empty reply eliminated** (root direct, override) | Root cause of "calendar prompts return empty": tool 403s → model retries → loop guard aborted to an **empty** message. Fix: (1) `llm/service/stream.py` loop guard now forces a **tool-free final turn** (`_force_no_tools`) instead of aborting — model relays the tool error in text. (2) `llm/tools/calendar.py` DRY'd 401 handling (`_mark_reauth`) + added `403 → _forbidden()` actionable message; **403 keeps the connector `active`** (only 401 → `needs_reauth`) so the tool stays offered. Verified live: calendar prompt now returns "enable the Calendar API + reconnect" guidance, connector stays active. Test gains a graceful-`done` regression assert. Unit 175✓; live sweep 12✓/2 skip. Docs: root+backend `CLAUDE.md`, `VERIFICATION_LAUNCH.md`; `graphify update .`. **Still a launch action:** enable Calendar API + `calendar.events` scope in Google Cloud, then reconnect. |
| 2026-06-22 | **Live tool + integration sweep SHIPPED** (root direct, override) | New `tests/live/test_tools_integrations.py` drives **every** agent-tool family + set-up connectors through real NIM. **12 pass / 2 skip.** Assertion = `tool_call` SSE + persisted `GET /tool-calls` row + `done` flags; confirm tools (`write_memory`/calendar write) asserted at sentinel, never executed. Enabled web search (compose `WEB_SEARCH_ENABLED` passthrough, **default false/opt-in**; searxng via `web-search` profile). **Finding:** Google **Calendar API 403** (scope/API not enabled in cloud console) — gating/dispatch correct, Drive works; tracked as launch action. Docs: backend `CLAUDE.md` + `VERIFICATION_LAUNCH.md`; `graphify update .`. |
| 2026-06-22 | **Verification + Launch scaffolding SHIPPED** (root direct, override) | Built + ran live: `pytest.ini`/`conftest.py` (4 markers, auto-skip), `tests/live/` HTTP E2E (**42 pass/3 skip** vs real NIM stack incl. RAG tool loop + grounding persistence), `tests/integration/` infra tier (migrations→047, `vector(1024)`, Neo4j/Redis), `scripts/smoke.sh` (**PASS**, 70B reply), `.github/workflows/ci.yml` (unit/retrieval/infra per-PR; live nightly), `tests/VERIFICATION_LAUNCH.md` runbook + launch checklist. Docs appended to backend+docker CLAUDE.md; `graphify update .`. No needs-root. |
| 2026-06-22 | **Verification + Launch scaffolding specced + delegated** (root direct) | 3 Explore agents (graphify-first) inventoried full backend surface, existing tests (~179 mocked + 26 retrieval), and prod-readiness. Pinned via AskUserQuestion: live NIM, NIM interim prod, runbook+scaffolding, all optional features live. Plan `~/.claude/plans/plan-out-a-verification-clever-catmull.md` approved → folded into HANDOFF as Phase V1+V2. (Then user overrode: root to implement directly — see row above.) |
| 2026-06-21 | **Phase 3c close-out — multi-task COMPLETE** (root direct) | needs-root done: `.env.example` Notifications section (`VAPID_PUBLIC_KEY`/`PRIVATE_KEY`/`SUBJECT`, `NOTIFICATION_RATE_LIMIT`/`WINDOW`); `ROADMAP.md` struck the image/onboarding/notifications gaps, struck #20/#21 in impl order + section headers, Dim 5 92%→95%, last-updated refreshed. Collapsed the whole finished sequence into a "Recently shipped" summary; HANDOFF idled. |
| 2026-06-21 | **Phase 3c — Notifications frontend ✅ → to root** (frontend worker) | `useNotificationPrefs.js` hook (prefs CRUD + push subscribe/unsubscribe); `public/sw.js` service worker; notification toggles in `SettingsModal`; `frontend/CLAUDE.md` updated. → mv `HANDOFF.md ../HANDOFF.md` (root close-out). |
| 2026-06-21 | **Phase 3c — Notifications backend ✅ → to frontend** (backend worker) | `models/notification.py` + migration 047; `api/notifications.py` (prefs CRUD, push subscribe, VAPID key); `services/notification.py` (email+push dispatch, Redis rate limit); ARQ jobs + wired callers; `run_digest` per-user `email_digest` gate; `config.py` VAPID vars; `pywebpush` deps; 8 tests pass. `backend/CLAUDE.md` updated. → mv `HANDOFF.md` to frontend (Phase 3c). |
