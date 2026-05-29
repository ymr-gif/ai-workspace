# ROADMAP — Multi-User AI Memory Platform

> Vision: A multi-user AI system where each person has a private, continuously evolving digital mind
> that unifies memory, reasoning, and future autonomous intelligence into one personalized cognitive workspace.

Last updated: 2026-05-30 (User Preference Extraction ✅ — Behavioral Pattern Tracker in progress)
**This document is subject to change.** Add, remove, or reprioritize features freely. Treat it as a living spec.

---

## How to Read This

**Build sequence:** Start at `Implementation Order` (bottom). Pick the next numbered item. Jump to its feature entry in the `Feature Backlog` section for concrete tasks. Pass to HANDOFF.

**Sections:**
- `Current State` — what is already built and working. Do not re-implement these.
- `Gap Analysis` — what is missing, grouped by which part of the vision it serves. Use this to understand *why* a feature matters before building it.
- `Feature Backlog` — one entry per feature: what it is, which files to touch, backend vs frontend split. This is the source of truth for HANDOFF task lists.
- `Implementation Order` — the recommended build sequence. Numbers = priority. Lower = build sooner.
- `Vision Alignment Score` — rough % coverage per dimension. Update after each feature ships.

**Priority tiers:**
- `P0` — core cognition. Builds the "private AI mind." Do these first.
- `P1` — platform completeness. Surfaces existing backends into UI; new unified capabilities.
- `P2` — autonomous agency. The system starts acting on behalf of the user.
- `P3` — long-term / future. Don't plan these yet.

**Dimensions** (used in Gap Analysis and Alignment Score) map to the five pillars of the vision:
1. Persistent Memory — the AI remembers and learns about the user over time
2. Unified Interface — one AI layer over files, memory, knowledge, conversations
3. Reasoning Loop — every response is contextual, grounded, and user-specific
4. Autonomous Agency — the system acts proactively, not just reactively
5. Real-Time Perception — the AI is aware of the user's live environment

---

## Current State (as of migration 032)

| Area | Status |
|------|--------|
| Multi-tier memory (sheet + history + project summary) | ✅ |
| Memory salience engine (per-fact scoring, decay, compaction) | ✅ |
| Memory conflict resolver (detect, suppress, resolve) | ✅ |
| Graph memory — Neo4j entity/relation extraction + keyword query | ✅ |
| Context budget allocator (priority-tiered, partial drop) | ✅ |
| Adaptive retrieval policy (factual/relational/temporal/broad) | ✅ |
| Hybrid retrieval — vector + BM25, RRF/weighted fusion, provenance | ✅ |
| File storage — SHA256 dedup, versioning, chunk quality states | ✅ |
| File formats — PDF, DOCX, XLSX, text/code/markdown | ✅ |
| AI agent tool loop (10 tools, ask_user, query_graph, write_memory) | ✅ |
| Autonomous memory writing (write_memory tool, user-confirm green card) | ✅ |
| Proactive suggestions + insight generation (ARQ background) | ✅ |
| Scheduled prompts (PromptTemplate, ScheduledPrompt) | ✅ |
| Workspace layer (isolated system prompts + workspace memory) | ✅ |
| Multi-tenant user isolation (all data scoped per user_id) | ✅ |
| Cost caps + rolling window billing per user | ✅ |
| Invite-gated registration, role-based access | ✅ |
| SSE streaming, Redis cache, circuit breaker, rate limiter | ✅ |
| Observability — Prometheus + Grafana (24 panels) | ✅ |

---

## Gap Analysis vs Vision

### Dimension 1 — Persistent Memory
| Gap | Notes |
|-----|-------|
| Behavioral pattern learning | No tracking of what user asks most, preferred style, domain habits |
| Preference extraction | No structured extraction of user preferences from conversations |
| Memory timeline/chronicle | No temporal view of how memory evolved across sessions |
| ~~Autonomous memory writing~~ | ~~AI reads memory but never writes it; all writes are user-triggered~~ ✅ |
| Cross-session continuity signal | No "last seen," session gap detection, or re-entry continuity summary |

### Dimension 2 — Unified Interface
| Gap | Notes |
|-----|-------|
| Unified search | No single endpoint spanning files + conversations + memory + graph |
| Knowledge graph explorer (UI) | Frontend shows entity/relation counts only; no visual graph |
| Memory timeline view (UI) | No chronological view of memory evolution in frontend |
| Cross-conversation knowledge propagation | Insights from conversations don't auto-write to memory |

### Dimension 3 — Reasoning Loop
| Gap | Notes |
|-----|-------|
| Intent classification | Router picks model type only; no user intent classification (question/task/exploration) |
| Grounding confidence signal | No indication to user of retrieval confidence or hallucination risk |
| Reasoning trace exposure | No chain-of-thought or intermediate reasoning steps in UI |

### Dimension 4 — Autonomous Agency
| Gap | Notes |
|-----|-------|
| Pattern detection | No recurring question/behavior detection to trigger proactive actions |
| User-defined scheduled agents | User can't define "check X every week and summarize" |
| Goal / task tracking | No persistent goal list the AI maintains on behalf of user |
| Event-driven triggers | No webhook/event system (file upload → trigger AI action) |
| Autonomous summarization push | Daily/weekly digest not yet user-configurable |

### Dimension 5 — Real-Time World Perception
| Gap | Notes |
|-----|-------|
| Web search tool | No internet search during chat |
| Live webpage ingestion | `ingest-url` exists but no live web fetch mid-conversation |
| External integrations | No calendar, email, or third-party data stream connectors |

### Platform / UX
| Gap | Notes |
|-----|-------|
| Memory conflict resolution UI | Backend complete; no frontend panel |
| Fact-level salience visualization | `facts[]` API exists; no UI rendering |
| Full data export / portability | Conversation export exists; no full memory + file export bundle |
| Image storage + indexing | Base64 image input works; images not persisted or searchable |
| User onboarding | No guided first-run experience |
| Push/email notifications | Insights in DB but not delivered outside the UI |

### Infrastructure
| Gap | Notes |
|-----|-------|
| Scheduled backup | `backup.sh` exists but not cron-scheduled |
| Horizontal scaling | Single-node; no k8s or multi-replica setup |

---

## Feature Backlog

Priority tiers: **P0** = core cognition · **P1** = platform completeness · **P2** = agency/autonomy · **P3** = future

---

### P0 — Core Cognition

#### ~~Autonomous Memory Writing~~ ✅
~~Allow AI to propose memory writes mid-conversation. Uses new `write_memory` tool in tool loop. On trigger, yields an `ask_user`-style confirmation card (green). On confirm, AI writes directly to `UserMemory.content`.~~
~~- Backend: `write_memory` tool in `llm/tools/`; memory write path already exists~~
~~- Frontend: green confirmation card variant distinct from amber ask_user~~

#### ~~User Preference Extraction~~ ✅
~~After every N conversations, ARQ job runs an LLM pass over recent history to extract preferences (verbosity, tone, domain vocabulary, response style). Writes structured result into `UserMemory.project_summary` or dedicated preference field.~~
~~- Backend: new ARQ job + summarizer module (`llm/summarizer/preferences.py`)~~

#### Behavioral Pattern Tracker
Track topics, query types, and tools engaged per user. Store as `UserBehaviorProfile` JSONB. Updated in background post-reply. Feeds adaptive retrieval policy (pre-warm) and agency.py hint generation.
- Backend: new `UserBehaviorProfile` model; background update in `api/chat/background.py`

#### Cross-Session Continuity Summary
On new conversation start (returning user), inject a brief re-entry summary: last active timestamp, last conversation topic, active goals. Computed from last conversation title + memory snapshot. No new model.
- Backend: `_build_stream_context()` addition; new `[LAST SESSION]` context block (low tier, drops first)
- Frontend: subtle "Welcome back" banner above first assistant message

---

### P1 — Platform Completeness

#### Memory Conflict Resolution UI
Surface `GET /memory/conflicts` in Memory panel. Per-conflict card: fact_a vs fact_b, conflict type badge (red=contradiction, yellow=duplicate, grey=ambiguous). Resolve buttons: Keep A / Keep B / Merge / Discard Both. Calls `POST /memory/conflicts/{id}/resolve`.
- Frontend only (backend complete)

#### Fact-Level Salience Panel
In Memory → View tab, render each fact line with a salience score bar (green ≥ 1.0, yellow 0.5–1.0, red < 0.5). Timestamp of last access. Uses existing `facts[]` array from `GET /memory`.
- Frontend only (backend complete)

#### Unified Search
`GET /api/search?q=&scope=all|files|conversations|memory|graph` fans out to all four stores in parallel, merges results with source labels and scores. Single UI search bar replaces per-panel search.
- Backend: new `api/search.py` router, parallel `asyncio.gather` across stores
- Frontend: global search bar in header

#### Knowledge Graph Explorer (UI)
Visual graph in Memory → Graph tab. Nodes = entities, edges = relations. Click node → panel shows linked facts and conversation references. Uses `GET /api/graph/sample` extended with pagination and type filter.
- Frontend: `react-force-graph` or `vis-network` canvas; replaces stats-only graph tab
- Backend: extend `GET /api/graph/sample` with `?limit=&entity_type=`

#### Memory Timeline View
Memory → History tab: chronological list of `UserMemoryVersion` snapshots. Expandable diff view per version (added lines green, removed lines red). Uses existing `GET /memory/history`.
- Frontend only (backend complete)

#### Full Data Export / Portability
`GET /api/export/full` returns a ZIP: all conversations (markdown), all files (originals), memory sheet, memory versions, graph entity dump. User-initiated. Streamed via `StreamingResponse`.
- Backend: new `api/export.py`, `zipfile` + `StreamingResponse`

#### Scheduled Backup (Infra)
APScheduler job in `scheduler_worker.py` calls `pg_dump` daily. Env var `BACKUP_SCHEDULE` (default `0 2 * * *`). Stores to `storage/backups/` with 7-day prune (matches existing `backup.sh` logic).
- Backend: scheduler entry; env var

---

### P2 — Autonomous Agency

#### Pattern Detection + Proactive Triggers
Post-reply: compare current query pattern against `UserBehaviorProfile`. If user has asked similar questions 3+ times, enqueue an ARQ insight: "You ask about X often — want me to create a summary document?" Extends `agency.py`.
- Backend: `agency.py` + behavior profile reader; ARQ job

#### User-Defined Scheduled Agents
User-facing CRUD for `ScheduledPrompt`: create/edit/delete via UI with natural-language schedule (daily/weekly/monthly), target workspace, and prompt. On trigger, injects into full chat pipeline.
- Backend: `ScheduledPrompt` CRUD API already partially exists; expose fully
- Frontend: new Automations panel (schedule picker, prompt editor, history)

#### Goal / Task Tracker
`UserGoal` model: title, description, status (active/completed/paused), linked conversation IDs. AI references active goals as `[ACTIVE GOALS]` context block (new tier between USER STATE and WORKSPACE STATE). User manages via Goals panel.
- Backend: new model + `api/goals.py`
- Frontend: Goals panel sidebar tab

#### Web Search Tool
`web_search(query)` tool in agent loop. Calls configurable backend (SearXNG self-hosted or Tavily API). Returns top 5 results as grounded context. Gated by `WEB_SEARCH_ENABLED` + `WEB_SEARCH_BACKEND` env vars.
- Backend: new tool in `llm/tools/`; optional SearXNG service in docker-compose

#### Event-Driven Triggers
`POST /api/webhooks/{user_token}` accepts external events. Payload routed to ARQ job that processes content and generates a `UserInsight`. Supports: `file.uploaded`, `reminder`, `external.data`.
- Backend: `api/webhooks.py`; ARQ job; `WebhookEvent` model; user token in `User` table

#### Daily/Weekly Digest
Scheduler job generates a weekly markdown summary (new files, memory changes, insights, goal progress) and delivers it as a `UserInsight` + optional email via SMTP. Configurable via `DIGEST_ENABLED`, `DIGEST_SCHEDULE`, `SMTP_*` env vars.
- Backend: scheduler job + email module; env vars

---

### P3 — Long-Term / Future

#### Live Webpage Ingestion (mid-chat)
`fetch_url(url)` tool: fetches live webpage via `httpx`, strips HTML with BeautifulSoup, chunks + embeds on the fly, injects as ephemeral `[WEB CONTEXT]`. Not stored as a File.
- Backend: new tool; `httpx` + `beautifulsoup4` deps

#### External Integrations
OAuth connectors for Google Drive, Notion, GitHub. ARQ polling jobs sync external content into file store. `ExternalSource` model tracks connector type, credentials, last sync.
- Backend: `ExternalSource` model; per-provider connector modules; OAuth flow

#### Image Storage + Indexing
Persist uploaded images as `File` records. Generate text captions via NIM vision endpoint at upload time. Embed captions for semantic search alongside text chunks.
- Backend: processor.py image path; caption generation tool; retriever extension

#### Voice Input
Browser `MediaRecorder` → `POST /api/transcribe` (Whisper/NIM ASR) → text injected as chat message. Optional TTS response for AI replies.
- Backend: transcription endpoint
- Frontend: mic button in chat input

#### Horizontal Scaling
Multi-replica API + ARQ workers via Docker Swarm or k8s Helm chart. Requires migrating `pg_advisory_xact_lock` → Redis-based distributed locks for memory write safety.
- Infra: compose scale config; Redis lock module replacing pg advisory locks

#### Multi-Modal Memory
Store image embeddings in pgvector. OCR + entity extraction from images. Graph extraction from image content. Unified retrieval across text + image modalities.
- Backend: processor.py + retriever + graph_memory extensions

---

## Implementation Order

```
P0 — now
  ~~1. Autonomous Memory Writing        closes the biggest gap ("private AI mind" that learns)~~ ✅
  ~~2. User Preference Extraction       personalizes every response~~ ✅
  3. Behavioral Pattern Tracker       feeds agency + adaptive retrieval
  4. Cross-Session Continuity Summary immediate UX win, very low cost

P1 — next sprint
  5. Memory Conflict Resolution UI    backend done, frontend only
  6. Fact-Level Salience Panel        backend done, frontend only
  7. Unified Search                   one interface to everything
  8. Knowledge Graph Explorer UI      high visual impact
  9. Memory Timeline View             backend done, frontend only
  10. Full Data Export                user trust / portability
  11. Scheduled Backup                ops reliability

P2 — following sprint
  12. User-Defined Scheduled Agents   ScheduledPrompt already exists, low lift
  13. Goal / Task Tracker             new model + UI, medium effort
  14. Pattern Detection + Triggers    builds on Behavioral Profile
  15. Web Search Tool                 gated by env var, isolated
  16. Daily/Weekly Digest             scheduler already wired

P3 — future
  17. Live Webpage Ingestion
  18. External Integrations
  19. Image Storage + Indexing
  20. Voice Input
  21. Horizontal Scaling
  22. Multi-Modal Memory
```

---

## Vision Alignment Score

| Dimension | Coverage | Blocker |
|-----------|----------|---------|
| 1. Persistent Memory | 80% | No behavioral patterns, no preference extraction |
| 2. Unified Interface | 55% | No unified search, no graph UI, no timeline UI |
| 3. Reasoning Loop | 65% | No grounding confidence, no intent classification |
| 4. Autonomous Agency | 35% | No patterns, no goals, no user-defined agents |
| 5. Real-Time Perception | 10% | No web search, no external integrations |
| **Overall** | **~50%** | P0 remaining + P1 would bring this to ~75% |
