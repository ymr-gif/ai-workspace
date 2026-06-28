# HANDOFF
- Updated: 2026-06-28
- Status: **Idle — no active task.** (Last shipped: Q3 Task A — abstention-biased Drive rules, root direct/override; measured ineffective, leak unchanged.) Next actionable: `QUEUE.md` Q3 **Task B** (now mandatory — see Pipeline).
- Owner: root.

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

## Pipeline

**Actionable now (parked by choice, NOT blocked):**
- **Drive over-fire fix** → `QUEUE.md` **Q3**. **Task A DONE 2026-06-28** (abstention-biased `_DRIVE_RULES` shipped + measured live: test-4 0/5, leak unchanged — prompt steering proven ineffective). **Task B (session-latched semantic gate that removes the Drive schema pre-intent) is now MANDATORY**, not conditional — its trigger (Task A test-4 unacceptable) fired. Cold-start-ready in Q3 (file map + verification runbook + pinned Redis latch storage + B0 eval-set spec). Bug tracked: `BUGS.md` open "Drive tools fire on greetings". **To activate:** root promotes Task B into this file → `mv` to `backend/`.

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
| 2026-06-28 | **Q3 Task A — abstention-biased Drive rules SHIPPED + measured ineffective** (root direct, override) | Rewrote `_DRIVE_RULES` (`backend/llm/tools/builtin/drive_tools.py`, one symbol — `_POST_LISTING`/`_drive_gate`/registrations untouched) to abstention-biased text; rebuilt api image; `graphify update .`. Live behavioral battery (admin, Drive-active, 5 trials/test, ground-truthed vs `tool_call_logs`): **T1 `ehllo` 0/5 no-fire · T2 `hello?` 0/5 · T3 real request 5/5 fires (correct) · T4 `thanks` 0/5** — `drive_list_files {}` fired on every greeting/ack turn, zero reduction. Confirms the schema (not the prompt) is causal. **Task B now mandatory** (was conditional on test-4 rate). Test convs + orphan tool-logs cleaned up; admin user-memory verified clean. Bug stays open. Docs: `BUGS.md`, `QUEUE.md` Q3, this file. |
| 2026-06-22 | **Calendar fully working — verified live** (root direct, override) | User enabled Calendar API + `calendar.events` scope in Google Cloud + reconnected the connector. Calendar now returns real events; `test_calendar_list_events` + `test_calendar_create_confirm_sentinel` **pass** (sweep now **13✓/1 skip**, only gmail skips). The 403 hardening + loop-guard graceful-reply fix stay as defense. Docs/memory marked resolved. |
| 2026-06-22 | **Calendar 403 UX fix — empty reply eliminated** (root direct, override) | Root cause of "calendar prompts return empty": tool 403s → model retries → loop guard aborted to an **empty** message. Fix: (1) `llm/service/stream.py` loop guard now forces a **tool-free final turn** (`_force_no_tools`) instead of aborting — model relays the tool error in text. (2) `llm/tools/calendar.py` DRY'd 401 handling (`_mark_reauth`) + added `403 → _forbidden()` actionable message; **403 keeps the connector `active`** (only 401 → `needs_reauth`) so the tool stays offered. Verified live: calendar prompt now returns "enable the Calendar API + reconnect" guidance, connector stays active. Test gains a graceful-`done` regression assert. Unit 175✓; live sweep 12✓/2 skip. Docs: root+backend `CLAUDE.md`, `VERIFICATION_LAUNCH.md`; `graphify update .`. **Still a launch action:** enable Calendar API + `calendar.events` scope in Google Cloud, then reconnect. |
| 2026-06-22 | **Live tool + integration sweep SHIPPED** (root direct, override) | New `tests/live/test_tools_integrations.py` drives **every** agent-tool family + set-up connectors through real NIM. **12 pass / 2 skip.** Assertion = `tool_call` SSE + persisted `GET /tool-calls` row + `done` flags; confirm tools (`write_memory`/calendar write) asserted at sentinel, never executed. Enabled web search (compose `WEB_SEARCH_ENABLED` passthrough, **default false/opt-in**; searxng via `web-search` profile). **Finding:** Google **Calendar API 403** (scope/API not enabled in cloud console) — gating/dispatch correct, Drive works; tracked as launch action. Docs: backend `CLAUDE.md` + `VERIFICATION_LAUNCH.md`; `graphify update .`. |
| 2026-06-22 | **Verification + Launch scaffolding SHIPPED** (root direct, override) | Built + ran live: `pytest.ini`/`conftest.py` (4 markers, auto-skip), `tests/live/` HTTP E2E (**42 pass/3 skip** vs real NIM stack incl. RAG tool loop + grounding persistence), `tests/integration/` infra tier (migrations→047, `vector(1024)`, Neo4j/Redis), `scripts/smoke.sh` (**PASS**, 70B reply), `.github/workflows/ci.yml` (unit/retrieval/infra per-PR; live nightly), `tests/VERIFICATION_LAUNCH.md` runbook + launch checklist. Docs appended to backend+docker CLAUDE.md; `graphify update .`. No needs-root. |
| 2026-06-22 | **Verification + Launch scaffolding specced + delegated** (root direct) | 3 Explore agents (graphify-first) inventoried full backend surface, existing tests (~179 mocked + 26 retrieval), and prod-readiness. Pinned via AskUserQuestion: live NIM, NIM interim prod, runbook+scaffolding, all optional features live. Plan `~/.claude/plans/plan-out-a-verification-clever-catmull.md` approved → folded into HANDOFF as Phase V1+V2. (Then user overrode: root to implement directly — see row above.) |
| 2026-06-21 | **Phase 3c close-out — multi-task COMPLETE** (root direct) | needs-root done: `.env.example` Notifications section (`VAPID_PUBLIC_KEY`/`PRIVATE_KEY`/`SUBJECT`, `NOTIFICATION_RATE_LIMIT`/`WINDOW`); `ROADMAP.md` struck the image/onboarding/notifications gaps, struck #20/#21 in impl order + section headers, Dim 5 92%→95%, last-updated refreshed. Collapsed the whole finished sequence into a "Recently shipped" summary; HANDOFF idled. |
| 2026-06-21 | **Phase 3c — Notifications frontend ✅ → to root** (frontend worker) | `useNotificationPrefs.js` hook (prefs CRUD + push subscribe/unsubscribe); `public/sw.js` service worker; notification toggles in `SettingsModal`; `frontend/CLAUDE.md` updated. → mv `HANDOFF.md ../HANDOFF.md` (root close-out). |
| 2026-06-21 | **Phase 3c — Notifications backend ✅ → to frontend** (backend worker) | `models/notification.py` + migration 047; `api/notifications.py` (prefs CRUD, push subscribe, VAPID key); `services/notification.py` (email+push dispatch, Redis rate limit); ARQ jobs + wired callers; `run_digest` per-user `email_digest` gate; `config.py` VAPID vars; `pywebpush` deps; 8 tests pass. `backend/CLAUDE.md` updated. → mv `HANDOFF.md` to frontend (Phase 3c). |
