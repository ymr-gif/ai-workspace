# Verification & Production Launch Runbook — NIM AI Gateway

Master, ordered runbook for proving the backend works end-to-end and launching it on the
NIM backend (interim prod). Extends the focused service/curl runbook in
[`VERIFICATION.md`](./VERIFICATION.md).

Last full verification: **2026-07-03** (rich full-feature run — all tiers + full-surface gap-filler
`tests/latch/rich_full.py`; report: `tests/latch/rich_full_logs/rich_full_report.md`). Previous:
2026-06-22 — see "Verification record" below.

---

## Test tiers

| Tier | Marker | Needs | Cost | Command |
|------|--------|-------|------|---------|
| T0 Unit | `unit` (default) | nothing | free | `pytest -m "not infra and not live_nim and not optional"` |
| Retrieval eval | — | nothing | free | `pytest tests/retrieval/` |
| T1 Infra | `infra` | Postgres+pgvector, Redis, Neo4j | free | `RUN_INFRA=1 pytest -m infra` |
| T2 Live E2E | `live_nim` | running stack + live model | $ | `RUN_LIVE_NIM=1 VERIFY_BASE_URL=… pytest -m live_nim` |
| T3 Optional | `optional` | per-feature creds/flags | $/free | `RUN_LIVE_NIM=1 VERIFY_BASE_URL=… pytest -m optional` |

Gating is automatic: an opt-in tier whose prerequisite is unmet **skips** (never fails), so a
plain `pytest` stays green on a laptop. Flip `RUN_INFRA` / `RUN_LIVE_NIM` to engage the heavier
tiers. `VERIFY_BASE_URL` defaults to `http://localhost:8000`.

---

## Phase 0 — offline (no services)

```bash
cd backend
pytest -m "not infra and not live_nim and not optional" -q   # unit tier (~175 tests)
pytest tests/retrieval/ -q                                   # retrieval eval (26)
```
Migration integrity (single head, ≥47 revisions) runs here too via `pytest -m infra` even
without a DB — those two checks need no service.

## Phase 1 — infra (real Postgres/Redis/Neo4j)

Run where the services are reachable (CI service containers, or inside the stack network):
```bash
DATABASE_URL=postgresql+asyncpg://scylla:scylla@localhost:5432/nimrouter \
REDIS_URL=redis://localhost:6379/0 \
NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=… \
RUN_INFRA=1 pytest -m infra -q
```
Asserts: pgvector installed, `message_embeddings.embedding` stays **vector(1024)**, core tables
present, DB at script head, Redis set/get/TTL + `SET NX` lock, Neo4j roundtrip + `entity_name_ft`.

> On a laptop where only the API/Neo4j ports are published, pg/redis tests auto-skip. Verify
> their facts directly instead:
> ```bash
> docker exec docker-postgres-1 psql -U scylla -d nimrouter -tA -c \
>   "SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attname='embedding';"  # → vector(1024)
> docker exec docker-postgres-1 psql -U scylla -d nimrouter -tA -c "SELECT version_num FROM alembic_version;"  # → 047
> docker exec docker-redis-1 redis-cli ping   # → PONG
> ```

## Phase 2 — live E2E (real model)

Stack up + healthy, then:
```bash
RUN_LIVE_NIM=1 VERIFY_BASE_URL=http://localhost:8000 pytest tests/live/ -q
```
Covers: SSE token streaming + full `done` contract, message/grounding persistence, conversation
continuity, non-stream `/chat`, model override, cache-bypass, **RAG tool loop** (upload → embed →
grounded answer citing the file), upload/dedup/delete, CRUD sweep (conversations/memory/goals/
scheduled-prompts/insights/integrations/usage/notifications), admin endpoints + secret masking,
auth lifecycle (login/register/API-key/revoke), health, metrics, 401 gating.

## Phase 3 — optional features

```bash
RUN_LIVE_NIM=1 VERIFY_BASE_URL=http://localhost:8000 pytest -m optional -q
```
Each self-skips when off on the target: web search (`WEB_SEARCH_ENABLED`), voice
(`VOICE_ENABLED`), web push (VAPID keys), Google OAuth (`INTEGRATION_SECRET` + `GOOGLE_*`).
Webhook roundtrip runs unconditionally.

## Phase 4 — post-deploy smoke (any environment)

```bash
bash backend/scripts/smoke.sh https://<host>      # exits non-zero on any failure
```
health → login → upload → one live `/chat/stream` turn → `/metrics` → cleanup.

---

## Production launch checklist (NIM interim prod)

**Pre-flight config (`.env`)**
- [ ] `JWT_SECRET_KEY` (≥32 chars), `NVIDIA_API_KEY` set, `LLM_BACKEND=nim`.
- [ ] `DATABASE_URL` → **pgBouncer** (not Postgres direct); `prepared_statement_cache_size=0`.
- [ ] Changed `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, `GF_SECURITY_ADMIN_PASSWORD` from defaults.
- [ ] `INTEGRATION_SECRET` (Fernet) + `INTEGRATION_REDIRECT_BASE`=prod domain if using OAuth.
- [ ] VAPID + SMTP vars if using push/digests.
- [ ] `nginx.prod.conf` domain set; firewall exposes only 80/443 (block 8000/3001/9090/7474).

**Bring-up & verify**
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- [ ] `docker compose ps` → all healthy; migrations at **047** (`SELECT version_num FROM alembic_version`).
- [ ] `bash backend/scripts/smoke.sh https://<host>` → SMOKE PASSED.
- [ ] `pytest -m "live_nim or optional"` against the prod URL (off-peak; small NIM spend).
- [ ] `/health` 200; Prometheus `/targets` green; Grafana dashboards load; 2 alert rules active
      (breaker trip, success<99%).
- [ ] Startup probe didn't pre-trip the breaker: `redis-cli KEYS "cb:open:*"` empty.
- [ ] `docker/backup.sh` produces a gzip dump; rehearse a restore in staging.

**Invariants — do not break**
- Never scale `scheduler` (no leader election → duplicate backups/emails/cron).
- Always go through pgBouncer (`AUTH_TYPE=plain` for pg16 SCRAM).
- Never `alembic stamp` without running the DDL.
- `INTEGRATION_SECRET` must be set before any OAuth use (else connector endpoints 503).
- Keep `import config` + `config.X` on the hot path (LLM_BACKEND live-toggle depends on it).

**Rollback**: `docker compose … down` → restore latest dump → `git checkout <prev tag>` →
rebuild api → `up -d`.

**First 24h**: tail `api`/`scheduler`/`arq-worker` logs; watch Grafana success-rate ≥99%, cost,
breaker; Postgres `pg_stat_activity` conn count + disk.

---

## Verification record — 2026-06-22 (live stack, NIM)

| Tier | Result |
|------|--------|
| Unit (existing + new config) | **175 passed**, 1 skipped |
| Live E2E (`tests/live/`, core) | **42 passed, 3 skipped** (voice / push off; web search since enabled) |
| Tool + integration sweep (`test_tools_integrations.py`) | **13 passed, 1 skipped** (Gmail not connected) |
| Endpoint contracts (`test_endpoints_extra.py`) | **10 passed** (templates, export, search, conv ops, invite, conflicts, re-embed, scheduled-prompt run) |
| Autonomy (`test_autonomy.py`) | **4 passed** (insights, compaction, graph extraction, auto-title) + A4/A5 DB-verified |
| Reliability (`test_reliability.py`) | **2 passed** (rate-limit 429, cost-cap 402) + D1/D2 breaker+fallback run-script |
| Smoke (`smoke.sh`) | **PASS** — 70B reply, `cost=$0.000242`, done contract complete |
| Infra facts (direct) | pgvector ✓, `vector(1024)` ✓, alembic **047** = head ✓, redis PONG ✓, `entity_name_ft` ✓ |
| Health | nim 791ms / embedding 944ms / redis / db all **ok** |

Notes:
- Streaming responses report `cache_hit=false` by design (stream serves fresh; caching applies
  to the internal cacheable path) — the `done.cache_hit` field is still asserted as a contract.
- Real endpoint paths differ from some older docs: insights `/insights`, integrations
  `/integrations`, vapid `/api/notifications/vapid-public-key` (404 when VAPID unset = push off).

---

## Tool & integration sweep — `tests/live/test_tools_integrations.py`

Exercises **every agent-tool family** + the set-up OAuth connectors through a real model.
Companion to the RAG-focused `test_files_rag.py`.

**Prerequisites**
- Stack up + `RUN_LIVE_NIM=1 VERIFY_BASE_URL=…`.
- **Web search** on: `WEB_SEARCH_ENABLED=true` **and** the searxng backend running:
  ```
  WEB_SEARCH_ENABLED=true docker compose -f docker/docker-compose.yml --profile web-search up -d searxng api
  ```
  (compose default is `false` — web search is opt-in and needs searxng; the `searxng` service is
  behind the `web-search` profile.) Verify JSON works: searxng must answer
  `GET /search?q=test&format=json` (the default image enables JSON in `docker/searxng/`).
- **Drive/Calendar/Gmail**: connected under the **admin** account (all three `active` since the
  2026-06-29 latch data collection; UI re-stub does NOT deactivate them); tests use admin headers
  and self-skip if a connector isn't `active`. `test_gmail_when_connected` passes live as of
  2026-07-03. `test_calendar_create_confirm_sentinel` is latch-first (cold create scores < the
  0.70 latch floor — schemas absent until a read-turn latches the session).

**Run**
```
cd backend
RUN_LIVE_NIM=1 VERIFY_BASE_URL=http://localhost:8000 pytest tests/live/test_tools_integrations.py -v -m "live_nim or optional"
```

**Assertion model** — a tool is proven three ways: the `tool_call` SSE event names it; `GET
/tool-calls?conversation_id=` shows the persisted `ToolCallLog` row; flag-bearing tools set
`done.web_searched` / `done.url_fetched`. Confirm-gated tools (`write_memory`, calendar writes)
are asserted at the **confirm sentinel** and never executed — no memory/calendar mutation.

**Coverage:** `web_search` (+negative gating proof), `fetch_url`, `list_files`, file-search
family, `query_graph`, `create_file`, `ask_user`, `write_memory` (confirm), Drive list/search,
calendar list + create (confirm). Gmail covered but self-skips (not connected).

### Verification record — 2026-06-22

| Suite | Result |
|-------|--------|
| `test_tools_integrations.py` (`live_nim` + `optional`) | **13 passed, 1 skipped** |

- **Calendar — RESOLVED 2026-06-22.** Earlier the connected account 403'd because the Calendar
  API/`calendar.events` scope weren't enabled in Google Cloud. After enabling both + reconnecting,
  `test_calendar_list_events` + `test_calendar_create_confirm_sentinel` pass live (real events
  returned). The 403 hardening remains as defense (tool returns `_forbidden()`, connector stays
  `active`, loop guard forces a tool-free final turn → actionable reply, never empty).
- `test_gmail_when_connected` — **skipped**: Gmail connector not set up in this environment.

---

## Full backend coverage — autonomous run (2026-06-23)

Extended live verification across the **non-tool** surface (autonomy, scheduler, admin
mutations, reliability invariants). Full item-by-item ledger + bug log: root `BUGS.md`
→ "Verification Coverage — Gaps" (V-A1…V-E5).

New suites (all `RUN_LIVE_NIM=1`): `test_endpoints_extra.py` (10), `test_autonomy.py` (4),
`test_reliability.py` (2). Plus run-script verifications for the unsafe/DB-only items
(circuit breaker + fallback via an isolated coder-breaker trip, admin env PUT/reload,
memory hard-reset + restore, behavior-profile + preference ARQ jobs via psql).

**Bugs found and fixed during the run:**
- **export Content-Length crash** (`api/export.py`) — `GET /export/full` aborted the
  connection; fixed (length from payload bytes).
- **REQUIRE_INVITE frozen import** (`auth/router.py`) — invite gate ignored `/admin/env`
  live reload; switched to call-time `config.REQUIRE_INVITE`.
- **scheduler ARQ pool never initialized** (`services/scheduler_worker.py`) — daily memory
  compaction + 6h integration sync silently no-op'd; added `init_arq_pool`.

**Open findings (logged in BUGS.md, need a decision — not auto-fixed):**
- **BUG-V3** (updated 2026-07-03) nonstream `POST /chat`: cap check added (`49cb6ea`) so capped users
  are blocked, but spend is still **unrecorded** (never accrues to the window); `/v1/chat/completions`
  has **neither** check nor accounting. Parked in BUGS.md → Open, needs decision.
- ~~**BUG-V6** scheduled in-container `run_backup` is dead~~ — **stale as of 2026-07-03**: the 2 AM
  scheduled backups ARE producing dumps (root-owned `nimrouter_*_020000.sql.gz` on 07-01/07-02).
  Host `bash docker/backup.sh` also works.
- **BUG-V7** `paddlepaddle` missing from the image → OCR (#19) would fail if enabled.
- **BUG-V2** `store_exchange` FK race (caught/logged) when a conversation is deleted before its
  async embed.

**Launch-relevant infra — verified 2026-07-03 (QUEUE Q5):** digest/notification email proven against
a MailHog dev relay (`docker compose --profile mail up -d mailhog`; SMTP on `mailhog:1025`, UI :8025);
web push proven end-to-end through real FCM (VAPID keypair via `/admin/env`, system Chrome over CDP —
Playwright's bundled Chromium cannot subscribe); pg-dump restore rehearsed into a scratch container
(26 tables, alembic 047). For prod: swap MailHog for a real SMTP provider + keep the VAPID keys.
