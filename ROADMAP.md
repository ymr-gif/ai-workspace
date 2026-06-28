# ROADMAP — Multi-User AI Memory Platform

> Vision: A multi-user AI system where each person has a private, continuously evolving digital mind
> that unifies memory, reasoning, and future autonomous intelligence into one personalized cognitive workspace.

Last updated: 2026-06-28 (P3 tail shipped — #20 Voice STT, #21 Horizontal Scaling (Redis-lock abstraction + multi-replica), Gmail (read) connector, onboarding wizard, out-of-UI notifications (email + web push); earlier #19 image CPU-OCR. Earlier: Google Calendar connector — read-write, confirm-card writes; P0 + P1 + P2 complete; P3 live webpage ingestion + external integrations; Reasoning Loop / Dim 3 hardened; Dim 2 closed; 2026-06-28 all five OAuth connectors moved to UI stubs (ENABLED_CONNECTOR_TYPES = []), Dim 5 pulled back to ~80%)
**This document is subject to change.** Add, remove, or reprioritize features freely. Treat it as a living spec.

> **Deployment direction (2026-06-17):** NIM is a test backend; the app is porting to a self-hosted
> home server (llama.cpp/GGUF; Mixtral 8x7B → 8x22B → eventual MoE, text-only). The port + the
> revised #19 plan (CPU PaddleOCR, not a VLM) are specced in `BUGS.md` → "Decisions — Home-Server
> Port & #19 Vision". The Calendar connector shipped; **#19 (Q2) image CPU-OCR shipped** (upload +
> chat paste, searchable, behind `IMAGE_OCR_ENABLED`). Q1 (Home-Server Port) is parked in `QUEUE.md`
> — box-independent work done, remainder blocked on the 2×P40 box. The backend config half is
> pre-staged behind an inert `LLM_BACKEND` flag (`nim`|`homeserver`); the tool_calls gate passed CPU-side.

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

## Current State (as of migration 041; P0 + P1 + P2 complete)

| Area | Status |
|------|--------|
| Multi-tier memory (sheet + history + project summary) | ✅ |
| Memory salience engine (per-fact scoring, decay, compaction) | ✅ |
| Memory conflict resolver (detect, suppress, resolve) | ✅ |
| Memory conflict resolution UI (Conflicts tab, type badges, resolve buttons) | ✅ |
| Fact-level salience panel (score bar + last-access timestamp per fact) | ✅ |
| Graph memory — Neo4j entity/relation extraction + keyword query | ✅ |
| Knowledge graph explorer UI (SVG circle-layout, click-to-highlight, filters) | ✅ |
| Context budget allocator (priority-tiered, partial drop) | ✅ |
| Adaptive retrieval policy (factual/relational/temporal/broad) | ✅ |
| Hybrid retrieval — vector + BM25, RRF/weighted fusion, provenance | ✅ |
| Unified search (`GET /api/search?scope=all\|files\|conversations\|memory\|graph`) | ✅ |
| File storage — SHA256 dedup, versioning, chunk quality states | ✅ |
| File formats — PDF, DOCX, XLSX, text/code/markdown | ✅ |
| Full data export (`GET /api/export/full` ZIP stream) | ✅ |
| AI agent tool loop (22 tools: file ops, graph, memory, web, drive, calendar; canvas removed) | ✅ |
| Web search tool (SearXNG/Tavily, heuristic-gated, `WEB_SEARCH_ENABLED` env var) | ✅ |
| Event-driven webhook triggers (`POST /webhooks/{user_token}`; `file.uploaded` / `reminder` / `external.data`; ARQ → UserInsight; `WebhookEvent` model; migration 040) | ✅ |
| Daily/weekly digest (APScheduler cron; per-user markdown summary of files/memory/insights/goals; delivered as `UserInsight` + optional SMTP email; `DIGEST_ENABLED` + `DIGEST_SCHEDULE` env vars; migration 041 adds `email` to users) | ✅ |
| Pattern detection + proactive triggers (`detect_recurring_patterns()`; 7-day dedup; ARQ enqueue with hint) | ✅ |
| Global autonomous agent canvas — Neo4j-backed node system (11 node types, typed ports, WIRED_TO relationships, agent scratchpad, boot diagnostics, per-session chat drawer) | ✅ |
| Autonomous memory writing (write_memory tool, user-confirm green card) | ✅ |
| User preference extraction (ARQ job every 50 msgs; `[PREFERENCES]` in UserMemory) | ✅ |
| Behavioral pattern tracker (`UserBehaviorProfile` JSONB; ARQ job every reply; feeds insight generation) | ✅ |
| Memory version history + diff view (History tab in Memory panel) | ✅ |
| Cross-session continuity summary (`[LAST SESSION]` tier-8 block; `done.last_session`; "Welcome back" banner) | ✅ |
| Proactive suggestions + insight generation (ARQ background; behavior-aware) | ✅ |
| User-defined scheduled agents (AutomationsPanel; CRUD + run history; cron support) | ✅ |
| Scheduled backup (APScheduler daily cron; `BACKUP_SCHEDULE` env var) | ✅ |
| ~~Workspace layer~~ — **removed** (collapsed to sessions only; migration 037) | ⌫ |
| Multi-tenant user isolation (all data scoped per user_id) | ✅ |
| Cost caps + rolling window billing per user | ✅ |
| Invite-gated registration, role-based access | ✅ |
| SSE streaming, Redis cache, circuit breaker, rate limiter | ✅ |
| Observability — Prometheus + Grafana (24 panels, 2 alert rules) | ✅ |

---

## Gap Analysis vs Vision

### Dimension 1 — Persistent Memory
| Gap | Notes |
|-----|-------|
| ~~Behavioral pattern learning~~ | ~~No tracking of what user asks most, preferred style, domain habits~~ ✅ |
| ~~Preference extraction~~ | ~~No structured extraction of user preferences from conversations~~ ✅ |
| ~~Memory timeline/chronicle~~ | ~~No temporal view of how memory evolved across sessions~~ ✅ |
| ~~Autonomous memory writing~~ | ~~AI reads memory but never writes it; all writes are user-triggered~~ ✅ |
| ~~Cross-session continuity signal~~ | ~~No "last seen," session gap detection, or re-entry continuity summary~~ ✅ |

### Dimension 2 — Unified Interface
| Gap | Notes |
|-----|-------|
| ~~Unified search~~ | ~~No single endpoint spanning files + conversations + memory + graph~~ ✅ |
| ~~Knowledge graph explorer (UI)~~ | ~~Frontend shows entity/relation counts only; no visual graph~~ ✅ |
| ~~Memory timeline view (UI)~~ | ~~No chronological view of memory evolution in frontend~~ ✅ |
| ~~Cross-conversation knowledge propagation~~ | ~~Insights from conversations don't auto-write to memory~~ ✅ top-3 `UserInsight` rows (30-day window) injected as `[RECENT INSIGHTS]` block between `[ACTIVE GOALS]` and `[PROJECT STATE]`; `stage:"insights"` in activity trace |

### Dimension 3 — Reasoning Loop
| Gap | Notes |
|-----|-------|
| ~~Intent classification~~ | ~~Router picks model type only; no user intent (question/task/exploration)~~ ✅ hybrid keyword + 8B fallback (`classify_intent_hybrid`); tunes retrieval breadth + tool eagerness |
| ~~Grounding confidence signal~~ | ~~No indication to user of retrieval confidence~~ ✅ `grounding` in `done` SSE (level + %); computed from `dense_score` (mode-independent), not skewed `final_score`. Persisted on `messages.render_meta` (migration 044) → badge survives refetch/reload/history. Themed dot, no emoji |
| ~~Reasoning trace exposure~~ | ~~No intermediate reasoning steps in UI~~ ✅ `activity[]` pipeline trace in `done` SSE + persisted `activity_trace`, expands from grounding badge (survives reload/history). Enhanced: `stage:"tool"` / `stage:"tool_result"` events emitted per tool call; retrieval detail includes top-3 `dense_score` values. NOTE: pipeline-level trace, not model chain-of-thought (llama-3.3-70b emits no native thinking tokens) |

### Dimension 4 — Autonomous Agency
| Gap | Notes |
|-----|-------|
| ~~Pattern detection~~ | ~~No recurring question/behavior detection to trigger proactive actions~~ ✅ |
| ~~User-defined scheduled agents~~ | ~~User can't define "check X every week and summarize"~~ ✅ |
| Goal / task tracking | No persistent goal list the AI maintains on behalf of user |
| ~~Event-driven triggers~~ | ~~No webhook/event system (file upload → trigger AI action)~~ ✅ |
| ~~Autonomous summarization push~~ | ~~Daily/weekly digest not yet user-configurable~~ ✅ |

### Dimension 5 — Real-Time World Perception
| Gap | Notes |
|-----|-------|
| ~~Web search tool~~ | ~~No internet search during chat~~ ✅ |
| ~~Live webpage ingestion~~ | ~~`ingest-url` exists but no live web fetch mid-conversation~~ ✅ |
| External integrations | OAuth connector backend complete (Drive read / Calendar rw / Gmail read / Notion / GitHub); all five are UI-stubs (`ENABLED_CONNECTOR_TYPES = []`). Re-expose by adding types to that array. Outlook/CalDAV not yet implemented. |

### Platform / UX
| Gap | Notes |
|-----|-------|
| ~~Memory conflict resolution UI~~ | ~~Backend complete; no frontend panel~~ ✅ |
| ~~Fact-level salience visualization~~ | ~~Partial — per-fact % badge rendered in View tab; no score bar or last-access timestamp yet~~ ✅ |
| ~~Full data export / portability~~ | ~~Conversation export exists; no full memory + file export bundle~~ ✅ |
| ~~Image storage + indexing~~ | ~~Base64 image input works; images not persisted or searchable~~ ✅ #19 CPU-OCR (upload + paste + scanned-PDF), searchable |
| ~~User onboarding~~ | ~~No guided first-run experience~~ ✅ `has_onboarded` flag + 3-step skippable wizard (Welcome → Email → Integrations) |
| ~~Push/email notifications~~ | ~~Insights in DB but not delivered outside the UI~~ ✅ email + web-push, per-user opt-in (digest / scheduled-completion / new-insight) |

### Infrastructure
| Gap | Notes |
|-----|-------|
| ~~Scheduled backup~~ | ~~`backup.sh` exists but not cron-scheduled~~ ✅ |
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

#### ~~Behavioral Pattern Tracker~~ ✅
~~Track topics, query types, and tools engaged per user. Store as `UserBehaviorProfile` (one row per user, JSONB `profile`). Updated via ARQ `update_behavior_profile_job` post-reply — no LLM, pure counter increments. Feeds `generate_user_insight()` in `agency.py` with richer behavioral context.~~
~~- Backend: `UserBehaviorProfile` model · migration 033 · `services/behavior.py` · ARQ job in `arq_worker.py` · trigger in `stream.py` · enhanced `agency.py` insight prompt~~

#### ~~Cross-Session Continuity Summary~~ ✅
~~On new conversation start (returning user), inject a brief re-entry summary: last active timestamp, last conversation topic. Computed from last conversation title. No new model.~~
~~- Backend: `_build_stream_context()` + tier-8 `[LAST SESSION]` block; emitted in `done` SSE as `last_session`~~
~~- Frontend: muted `✦ Last session: "…" — X ago` banner above first AI bubble; auto-dismisses 8s~~

---

### P1 — Platform Completeness

#### ~~Memory Conflict Resolution UI~~ ✅
~~Surface `GET /memory/conflicts` in Memory panel. Per-conflict card: fact_a vs fact_b, conflict type badge (red=contradiction, yellow=duplicate, grey=ambiguous). Resolve buttons: Keep A / Keep B / Merge / Discard Both. Calls `POST /memory/conflicts/{id}/resolve`.~~
~~- Frontend only (backend complete)~~

#### ~~Fact-Level Salience Panel~~ ✅
~~Per-fact salience % badge already rendered in View tab (color-coded green/amber/grey). Remaining: replace badge with a visual score bar, add last-access timestamp per fact. Uses existing `facts[]` array from `GET /memory`.~~
~~- Frontend only (backend complete)~~

#### ~~Unified Search~~ ✅
~~`GET /api/search?q=&scope=all|files|conversations|memory|graph` fans out to all four stores in parallel, merges results with source labels and scores. Single UI search bar replaces per-panel search.~~
~~- Backend: new `api/search.py` router, parallel `asyncio.gather` across stores~~
~~- Frontend: global search bar in header~~

#### ~~Knowledge Graph Explorer (UI)~~ ✅
~~Visual graph in Memory → Graph tab. Nodes = entities, edges = relations. Click node → panel shows linked facts and conversation references. Uses `GET /api/graph/sample` extended with pagination and type filter.~~
~~- Frontend: `react-force-graph` or `vis-network` canvas; replaces stats-only graph tab~~
~~- Backend: extend `GET /api/graph/sample` with `?limit=&entity_type=`~~

#### ~~Memory Timeline View~~ ✅
~~Memory → History tab: chronological list of `UserMemoryVersion` snapshots. Expandable diff view per version (added lines green, removed lines red). Uses existing `GET /memory/history`.~~
~~- Frontend only (backend complete)~~

#### ~~Full Data Export / Portability~~ ✅
~~`GET /api/export/full` returns a ZIP: all conversations (markdown), all files (originals), memory sheet, memory versions, graph entity dump. User-initiated. Streamed via `StreamingResponse`.~~
~~- Backend: new `api/export.py`, `zipfile` + `StreamingResponse`~~

#### ~~Scheduled Backup (Infra)~~ ✅
~~APScheduler job in `scheduler_worker.py` calls `pg_dump` daily. Env var `BACKUP_SCHEDULE` (default `0 2 * * *`). Stores to `storage/backups/` with 7-day prune (matches existing `backup.sh` logic).~~
~~- Backend: scheduler entry; env var~~

---

### P2 — Autonomous Agency

#### ~~Pattern Detection + Proactive Triggers~~ ✅
~~Post-reply: compare current query pattern against `UserBehaviorProfile`. If user has asked similar questions 3+ times, enqueue an ARQ insight: "You ask about X often — want me to create a summary document?" Extends `agency.py`.~~
~~- Backend: `detect_recurring_patterns()` in `agency.py`; 7-day dedup guard; ARQ enqueue with hint kwarg~~

#### ~~User-Defined Scheduled Agents~~ ✅
~~User-facing CRUD for `ScheduledPrompt`: create/edit/delete via UI with natural-language schedule (daily/weekly/monthly), target workspace, and prompt. On trigger, injects into full chat pipeline.~~
~~- Backend: `ScheduledPrompt` CRUD API already partially exists; expose fully~~
~~- Frontend: new Automations panel (schedule picker, prompt editor, history)~~

#### ~~Goal / Task Tracker~~ ✅
~~`UserGoal` model: title, description, status (active/completed/paused), linked conversation IDs. AI references active goals as `[ACTIVE GOALS]` context block (new tier between USER STATE and PROJECT STATE). User manages via Goals panel.~~
~~- Backend: new model + `api/goals.py`~~
~~- Frontend: Goals panel sidebar tab~~

#### ~~Global Autonomous Agent Canvas~~ ✅ (NEW-2026-05-31)
~~Neo4j-backed canvas graph giving the AI a structured self-model of its environment. 11 typed node types with input/output ports. `WIRED_TO` relationships with port validation. Agent scratchpad (`UserMemory.agent_scratchpad` JSONB) for cross-session context. Boot diagnostics on agent init (model health + canvas restore). 7 new tools: `create_canvas_node`, `delete_canvas_node`, `update_canvas_node`, `wire_nodes`, `unwire_nodes`, `query_canvas`, `get_canvas_graph`.~~
~~- Backend: `backend/agent/` (node.py, canvas_graph.py, boot.py) · `backend/core/neo4j_client.py` (+1 index) · `backend/models/user.py` (+agent_scratchpad) · `backend/alembic/versions/036_agent_scratchpad.py` · `backend/llm/tools/schemas.py` (+7 schemas) · `backend/llm/tools/executor.py` (+7 dispatch branches) · `backend/llm/service/context.py` (boot + registry injection) · `backend/api/chat/helpers.py` (boot call + scratchpad save)~~
~~- Zero conflicts: distinct Neo4j label (`CanvasNode` vs `Entity`), prefixes on all tool names (`canvas_*`), separate Redis cache key (`canvas:{uid}`), append-only to UserMemory~~

#### ~~Web Search Tool~~ ✅
~~`web_search(query)` tool in agent loop. Calls configurable backend (SearXNG self-hosted or Tavily API). Returns top 5 results as grounded context. Gated by `WEB_SEARCH_ENABLED` + `WEB_SEARCH_BACKEND` env vars.~~
~~- Backend: new tool in `llm/tools/`; optional SearXNG service in docker-compose~~

#### ~~Event-Driven Triggers~~ ✅
~~`POST /api/webhooks/{user_token}` accepts external events. Payload routed to ARQ job that processes content and generates a `UserInsight`. Supports: `file.uploaded`, `reminder`, `external.data`.~~
~~- Backend: `api/webhooks.py`; ARQ job; `WebhookEvent` model; user token in `User` table~~

#### ~~Daily/Weekly Digest~~ ✅
~~Scheduler job generates a weekly markdown summary (new files, memory changes, insights, goal progress) and delivers it as a `UserInsight` + optional email via SMTP. Configurable via `DIGEST_ENABLED`, `DIGEST_SCHEDULE`, `SMTP_*` env vars.~~
~~- Backend: scheduler job + email module; env vars~~

---

### P3 — Long-Term / Future

#### ~~Live Webpage Ingestion (mid-chat)~~ ✅
~~`fetch_url(url)` tool: fetches live webpage via `httpx`, strips HTML with BeautifulSoup, chunks + embeds on the fly, injects as ephemeral `[WEB CONTEXT]`. Not stored as a File.~~
~~- Backend: new tool; `httpx` + `beautifulsoup4` deps~~

#### ~~External Integrations~~ ✅
~~OAuth connectors for Google Drive, Notion, GitHub. ARQ polling jobs sync external content into file store. `ExternalSource` model tracks connector type, credentials, last sync.~~
~~- Backend: `ExternalSource` model; per-provider connector modules; OAuth flow~~
~~- Frontend: IntegrationsPanel; OAuth popup flow; status/sync UI~~

#### Image Storage + Indexing ✅ (2026-06-21)
Persist uploaded images as `File` records. Extract text via **CPU OCR (PaddleOCR)** at upload (chat model is text-only on the home server — no VLM caption). Embed the OCR text for semantic search alongside text chunks; both Library uploads and inline `image_b64` chat paste route through OCR.
- ~~Backend: processor.py image path (`_extract_image`/`extract_image_from_bytes`); `File.media_type`/`ocr_text` + migration 045; `IMAGE_OCR_ENABLED` gate; paste-path unify (`stream.py`)~~ ✅
- ~~Scanned-PDF fallback (Q-C5): `_extract_pdf` → blank text + gate on → pypdfium2 render → PaddleOCR per page (`_PDF_OCR_MAX_PAGES=20`)~~ ✅
- ~~Frontend: image thumbnail + `ocr_text` snippet (FilesPanel), Preview tab (FileViewer), `img` search badge~~ ✅
- Revised approach + full to-do: `BUGS.md` decisions (Q-C*) and `QUEUE.md` Q2. (Earlier VLM-caption draft superseded.)

#### Voice Input ✅ (STT, 2026-06-21)
Browser `MediaRecorder` → `POST /api/transcribe` → text injected into chat input. **STT only** (TTS deferred).
- ~~Backend: transcription endpoint (`VOICE_ENABLED`-gated, stub transcriber)~~ ✅ — real Whisper/ASR parked in `QUEUE.md` Q2 (box-blocked)
- ~~Frontend: mic button in chat input~~ ✅

#### Horizontal Scaling ✅ (2026-06-21)
Multi-replica API + ARQ workers. Migrates `pg_advisory_xact_lock` → optional Redis distributed lock for memory write safety.
- ~~Infra: compose scale config; Redis lock module~~ ✅ — `core/locks.py` `user_write_lock` behind inert `MEMORY_LOCK_BACKEND` (pg|redis, default pg); API `--scale` (stateless); scheduler singleton; nginx dynamic DNS

#### Multi-Modal Memory
Store image embeddings in pgvector. OCR + entity extraction from images. Graph extraction from image content. Unified retrieval across text + image modalities.
- Backend: processor.py + retriever + graph_memory extensions

---

## Implementation Order

```
P0 — now
  ~~1. Autonomous Memory Writing        closes the biggest gap ("private AI mind" that learns)~~ ✅
  ~~2. User Preference Extraction       personalizes every response~~ ✅
  ~~3. Behavioral Pattern Tracker       feeds agency insight generation~~ ✅
  ~~4. Cross-Session Continuity Summary immediate UX win, very low cost~~ ✅

P1 — next sprint
  ~~5. Memory Conflict Resolution UI    backend done, frontend only~~ ✅
  ~~6. Fact-Level Salience Panel        partial — badge done, bar + timestamp remaining~~ ✅
  ~~7. Unified Search                   one interface to everything~~ ✅
  ~~8. Knowledge Graph Explorer UI      high visual impact~~ ✅
  ~~9. Memory Timeline View            backend done, frontend only~~ ✅
  ~~10. Full Data Export                user trust / portability~~ ✅
  ~~11. Scheduled Backup                ops reliability~~ ✅

P2 — following sprint
  ~~12. User-Defined Scheduled Agents   ScheduledPrompt already exists, low lift~~ ✅
   ~~13. Goal / Task Tracker             new model + UI, medium effort~~ ✅
   ~~14. Pattern Detection + Triggers    builds on Behavioral Profile~~ ✅
   ~~15. Global Autonomous Agent Canvas  Neo4j-based node system; 11 node types; typed ports; agent scratchpad; boot diagnostics; 7 new canvas tools~~ ✅ (NEW-2026-05-31)
   ~~16. Web Search Tool                 gated by env var, isolated~~ ✅
   ~~17. Event-Driven Triggers           webhook + ARQ + WebhookEvent model~~ ✅
   ~~18. Daily/Weekly Digest             scheduler + email module + SMTP config~~ ✅

P3 — future
  ~~17. Live Webpage Ingestion~~ ✅
  ~~18. External Integrations~~ ✅
  ~~19. Image Storage + Indexing~~ ✅
  ~~20. Voice Input~~ ✅ (STT; real ASR parked — QUEUE Q2)
  ~~21. Horizontal Scaling~~ ✅
  22. Multi-Modal Memory          trigger-gated (BUGS Q-D2) — build only on the trigger
```
+ Gmail (read) connector · Onboarding wizard · Out-of-UI notifications (email + web push) — shipped 2026-06-21

---

## Vision Alignment Score

| Dimension | Coverage | Blocker |
|-----------|----------|---------|
| 1. Persistent Memory | 97% | P0 complete |
| 2. Unified Interface | 100% | Cross-conversation insight propagation shipped (`[RECENT INSIGHTS]` block) |
| 3. Reasoning Loop | ~97% | Tool call trace + retrieval scores added; model chain-of-thought not exposed (no native thinking tokens — hard model constraint) |
| 4. Autonomous Agency | 90% | P2 complete; goal tracker ✅ |
| 5. Real-Time Perception | ~80% | Web search + live fetch + #19 image CPU-OCR + out-of-UI notifications done; OAuth connector backend complete (Drive/Calendar/Gmail/Notion/GitHub) but all UI-stubbed; Outlook/CalDAV not implemented |
| **Overall** | **~97%** | P0–P2 complete; P3 done (#19 OCR, voice STT, onboarding, notifications); horizontal-scaling lock abstraction shipped; Dim 3 ~97% (model CoT ceiling); Dim 5 pulled back — connectors UI-stubbed; remaining: Outlook/CalDAV, real ASR + home-server box |
