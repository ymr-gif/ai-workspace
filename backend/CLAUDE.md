# Backend Reference

## Graphify — Mandatory Navigation Rule

`graphify-out/graph.json` exists at project root. **NEVER grep or read source files for codebase exploration without first running graphify query.**

- `graphify query "<question>"` — scoped subgraph for any codebase question
- `graphify path "<A>" "<B>"` — relationship between two concepts
- `graphify explain "<concept>"` — focused explanation of a node
- Raw file reads only after graphify has oriented you, or to modify/debug specific lines
- After any code change: `graphify update .` (AST-only, no API cost)
- Applies to subagents — include this rule in every subagent prompt involving code exploration

---

## Structure
```
├── main.py                 — lifespan, middleware, router includes
├── config.py               — env vars loaded from ../.env via find_dotenv()
├── models/                 — ORM (26 classes: Invitation, User, UserInsight, AdminAuditLog, UserMemory, MemoryConflict, UserMemoryVersion, UserBehaviorProfile, UserGoal, WebhookEvent, ExternalSource, File, FileChunk, FileVersion, Conversation, Message, MessageEmbedding, ConversationFile, ToolCallLog, PromptTemplate, ScheduledPrompt, ScheduledPromptRun, UserNotificationPreferences, PushSubscription, SystemConfig; Conversation has is_archived/archived_at)
├── alembic/versions/       — 047 migrations; latest: 047_notification_tables.py (UserNotificationPreferences + PushSubscription)
├── auth/                   — JWT, bcrypt (direct, no passlib), API key fallback (SHA-256 hashed), invite validation
├── tests/
│   ├── test.py + test_memory_hygiene.py + test_content_filter.py + test_drive.py + test_gmail.py + test_reasoning_loop.py + test_image_ocr.py + test_pdf_ocr.py + test_voice.py — 104 tests (36 memory hygiene, 12 content filter, 11 drive, 11 gmail, 11 reasoning loop, 9 image OCR, 9 PDF OCR, 4 voice STT, 1 circuit breaker)
│   ├── retrieval/conftest.py + test_hybrid_eval.py — 26 tests, mock DB, no NIM
│   ├── {drive,calendar,gmail}_intent_eval.jsonl — 40 lines each (20 pos + 20 easy-neg); latch threshold tuning sets
│   └── latch/ — connector-intent latch data-collection harness (Phase 0→2): agent_capture.py (API) + ui_capture.py (Playwright UI twin) write labeled capture rows; measure.py joins them with `latch_score` logs → outputs A/B/C + emits eval sets; prompt_bank.py (hard-band prompts); README.md. Runbook: `plans/latch-data-session-kickoff.md`
├── llm/
│   ├── service/            — context build, context budget allocator, SSE stream + tool loop (MAX_TOOL_ITERATIONS=60); paste-path OCR injection (image_b64 → OCR text → context, no model_vision needed when IMAGE_OCR_ENABLED=true)
│   ├── nim.py              — NIM API call, accumulates tool_call deltas
│   ├── tools/              — 22 tool schemas + execute_tool(); sync I/O via asyncio.to_thread()
│   │   ├── schemas.py, registry.py (TOOL_REGISTRY + register_tool/run_tool), executor.py (shim → run_tool), file_ops.py, search.py, drive.py, calendar.py, gmail.py, fetch_url.py
│   │   └── builtin/         — side-effect registration; __init__ imports file_tools, memory_tools, web_tools, drive_tools, **calendar_tools**, **gmail_tools** (each calls register_tool() on import — a module omitted here = its tools silently absent from the registry)
│   ├── graph_memory.py     — Neo4j extraction (70B model) + query_by_keywords; entity caps: _MAX_ENTITY_NAME_LEN=200, _MAX_ENTITIES_PER_CALL=30, _MAX_RELS_PER_CALL=60, _MAX_USER_ENTITIES=500 (evicts oldest by updated_at); cache key SHA256[:32]; _cache_del_user() busts on write; skips if compact:running:{user_id} Redis lock held; MERGE SET preserves specific type over OTHER; merge_duplicate_entities() has second pass for substring/token-subset same-type dedup with rel preservation
│   ├── router.py / circuit_breaker.py / embeddings.py — classify, circuit, embed; `classify_intent()` keyword fast-path + `classify_intent_hybrid()` (one cheap 8B call only on ambiguous/no-signal; try/except → "question") → task|exploration|question
│   ├── retriever/          — hybrid vector+BM25 fusion (rrf|weighted); debug param; fusion.py, queries.py, main.py, attachments.py. `retrieve_global` (cross-conv pool) applies a similarity floor (_GLOBAL_SIM_FLOOR=0.30) + recency decay (_RECENCY_HALF_LIFE_DAYS=14, 0.5^(age_days/half_life) on MessageEmbedding.created_at) and re-ranks by weighted score before fusion; within-conv `retrieve()` unweighted
│   ├── summarizer/         — memory compression, compaction; prompts.py, memory.py, history.py, project.py, compact.py; compact.py:_prune_canvas_corrections uses _CANVAS_BLOCKLIST regex + _ALLOWLIST_SUBSTRINGS guard
│   └── agency.py           — proactive suggestions + insight generation (ARQ)
├── cache/                  — Redis primary + LRU fallback; cache-bypass on file/image/model-param
├── core/                   — db (pgbouncer: prepared_statement_cache_size=0), redis, arq, neo4j (get_health; pool size=20, timeout=5s)
├── rate_limiter/           — sliding-window per user + per-model; reuses request.state.current_user; logs warning on fail-open (Redis down)
├── observability/          — Prometheus counters/histograms; Redis-stream metrics worker; multiprocess mode via PROMETHEUS_MULTIPROC_DIR
├── services/
│   ├── notification.py     — notify() dispatch: load prefs, rate-limit, email + web push per channel toggle; lazy-create UserNotificationPreferences with defaults
├── api/
│   ├── notifications.py    — GET/PATCH /api/notifications/preferences, POST /api/notifications/push/subscribe, GET /api/notifications/vapid-public-key
│   ├── chat/
│   │   ├── __init__.py     — combines router + stream_router
│   │   ├── schemas.py      — ChatRequest model
│   │   ├── router.py       — POST /chat (non-streaming)
│   │   ├── stream.py       — POST /chat/stream SSE endpoint + event_generator; status="partial" for mid-stream breaks (STREAM_INTERRUPTIONS counter); ALL_MODELS_FAILED counter; saves `pending_question` from `ask_user` event as assistant message content. **Activity trace:** emits `{type:"status", stage, detail, level, ms?}` events for every pipeline step — context-build stages come from `ctx["activity"]` (seeded in `_build_stream_context`, error-surfaced not silently swallowed), live stages (cache/route/budget/model_call/fallback/tool/tool_result) from `generate_stream`; accumulated into `activity` and persisted as `messages.activity_trace` (JSONB) on the assistant message (done **and** `_persist_abort`). Returned by `GET /conversations/{id}/messages`. No-silent-failures: traced stages emit `level:"error"` instead of `except: pass`.
│   │   ├── helpers.py      — context build, model resolve, cost cap; auto-resolves expired MemoryConflicts (keep_a); time-based fact salience decay in ranking (not persisted); query embedded conditionally via _is_trivial() (≤2‑word/greetings skip embed — saves API cost); embed_status (ok/failed/skipped) tracked in context dict + activity trace; global file fallback: when no files explicitly attached, retrieves from ALL user ready files so Drive-synced content is searchable without manual attachment
│   │   └── background.py   — auto-title, embed, proactive, token/cost calc; _auto_title uses atomic UPDATE...WHERE title=:default (no TOCTOU race)
│   ├── files/              — upload (sets media_type by extension), ingest-url, search, versions; sha256 dedup
│   ├── conversations/      — list (?q=), export, PATCH, delete; file attach/detach
│   │   ├── __init__.py     — combines crud + files sub-routers
│   │   ├── crud.py         — list, messages, PATCH, export, delete
│   │   └── files.py        — attach/detach files
│   ├── admin/              — require_role("admin"); users, cost-limit, audit-log, env mgmt
│   │   ├── __init__.py     — combines all sub-routers
│   │   ├── utils.py        — _audit(), _user_row(), _fetch_user_stats(), _mask()
│   │   ├── users.py        — GET/PATCH user routes
│   │   ├── audit.py        — GET /audit-log
│   │   ├── env.py          — GET/PUT env vars, reload
│   │   ├── system.py       — POST /re-embed
│   │   └── memory.py       — POST /memory/reset (soft/hard); _soft_reset includes _purge_canvas_entities() Neo4j cleanup; GET /memory/versions?user_id= (snapshot list) + POST /memory/restore {user_id,version_id,confirm:"RESTORE <id>"} (reversible rollback — snapshots current sheet before overwriting from a user_memory_versions row; audits memory.restore)
│   ├── graph.py            — /graph/stats, /health, /sample (?limit=1-200, ?entity_type=); DELETE /graph/entities/{name}; POST /graph/prune (removes long names + stale OTHER-type entities >7 days)
│   ├── system.py           — /health, /metrics, /hardware + /system/hardware alias (both serve CPU/RAM/GPU/disk/uptime — psutil + pynvml); probe_models_on_startup() pings all MODELS, pre-trips circuit on failure
│   ├── memory.py           — GET /memory returns active_conflicts count; scan_conflicts sets expires_at=+7d; conflicts auto-resolved keep_a after expiry
│   ├── export.py            — GET /export/full; builds ZIP in memory with conversations/files/memory/graph data
│   ├── search.py            — GET /api/search unified search; fans out to files/conversations/memory/graph via asyncio.gather; file search selects FileModel.id.label("file_id") to avoid column name collision with FileChunk.id
│   ├── goals.py             — CRUD for UserGoal; status filter, conversation linking
│   ├── scheduled_prompts.py — CRUD for user-defined automated prompts; schedule alias support (daily/weekly/monthly); POST /run trigger
│   ├── transcribe.py         — POST /api/transcribe (multipart UploadFile, VOICE_ENABLED gate, stub ASR)
│   ├── webhooks.py          — POST /api/webhooks/{user_token} (public, no auth); GET/POST/DELETE /auth/me/webhook-token; WebhookEvent insert + ARQ enqueue
├── services/
│   ├── processor.py        — extract→chunk→embed; CPU work in asyncio.to_thread(); _extract_pdf falls back to pypdfium2 OCR when blank + IMAGE_OCR_ENABLED; _extract_image uses PaddleOCR; _PDF_OCR_MAX_PAGES=20
│   ├── transcribe.py        — async transcribe_audio(data, mime_type, *, language) dispatches on ASR_BACKEND; stub returns placeholder
│   ├── arq_worker.py       — _MAX_TRIES=4 (5s/30s/120s); ARQ_JOB_FAILED counter on final failure for all jobs; process_file_job sets upload_status="error" on final failure; WorkerSettings has on_startup/on_shutdown that init/close llm_client.client (httpx) — required for embeddings in worker process; sync job enqueues process_file_job via ctx["redis"].enqueue_job() (NOT asyncio.create_task — tasks silently fail in ARQ context)
│   ├── re_embed.py         — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py     — fuzzy-patch, save-version-before-mutate; sync I/O in asyncio.to_thread()
│   └── scheduler_worker.py — APScheduler cron runner; daily memory compaction at 3 AM UTC; backup via BACKUP_SCHEDULE env (default 2 AM UTC)
│   └── integrations/
│       ├── base.py         — AbstractConnector ABC, OAuthTokens/ConnectorCredentials/SyncedChunk TypedDicts
│       ├── registry.py     — @register decorator, REGISTRY dict, get_connector()
│       ├── google_oauth.py — GoogleOAuthConnector(AbstractConnector) base with get_auth_url/exchange_code/refresh_tokens
│       ├── google_drive.py — GoogleDriveConnector(GoogleOAuthConnector) SCOPE=drive.readonly, connector_type="google_drive"
│       ├── google_calendar.py — GoogleCalendarConnector(GoogleOAuthConnector) SCOPE=calendar.events, connector_type="google_calendar"
│       ├── gmail.py         — GmailConnector(GoogleOAuthConnector) SCOPE=gmail.readonly, connector_type="gmail"
│       ├── notion.py       — NotionConnector
│       └── github.py       — GitHubConnector
├── storage/                — SHA256 streaming write
├── requirements.txt        — added psutil + nvidia-ml-py for /hardware endpoint; pypdfium2 for scanned-PDF OCR
└── HANDOFF_PROTOCOL.md     — worker handoff protocol (shared from root)
```

---

## Key Models
- **User**: cost_limit_usd/cost_window_days cap, api_key auth, is_active gate
- **File**: sha256_hash dedup `(user_id, hash)`; `media_type` (text|document|image|spreadsheet|null) + `ocr_text` (nullable, image/scanned-PDF OCR output)
- **Message**: content_tsv GIN for full-text search; tracks token + cost; `token_estimate` (bool, nullable) — true = character-heuristic backfill (migration 032), null = real NIM data; `render_meta` JSONB (nullable, migration 044) — grounding badge payload `{grounding, query_type, src_count}` persisted on the assistant message so the badge survives the post-send refetch + reload + history (built once via `_build_render_meta()` in `api/chat/stream.py`, returned by `GET /conversations/{id}/messages`)
- **SystemConfig**: key/value store — tracks MODEL_EMBEDDING for re-embed triggers
- Others: more in `models/` (chat, file, memory, tools, scheduled, auth)
- **UserBehaviorProfile**: one row per user, JSONB `profile` with `query_types / topic_keywords / tools_used / models_used / total_messages`; updated via ARQ `update_behavior_profile_job` post-reply; feeds `generate_user_insight()`; migration 033
- **WebhookEvent**: `id` UUID PK, `user_id` FK, `event_type` (file.uploaded/reminder/external.data), `payload` JSONB, `status` (pending/processed/error), `error` Text, `created_at`, `processed_at`; migration 040
- **User.email**: nullable String(256), unique, indexed; set via `PATCH /auth/me/email`; used by digest email delivery; migration 041
- **User.has_onboarded**: Boolean, default false, not-null; set via `POST /auth/me/onboarding-complete`; migration 046
- **UserMemory**: has `agent_scratchpad` JSONB (nullable) from migration 036 — unused since canvas removal

---

## ChatRequest
`message` (str, max 2000) · `conversation_id` · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type`
`file_ids` (list[str], default []) — explicit file UUIDs to attach per-request; merged with conversation-attached files in `helpers.py`; ownership-checked against `current_user.id` before use; triggers embedding + reasoning model (70B) same as conversation files

---

## AI Agent Tool Loop

### Tool activation — capability gating + native function calling (since 2026-06-23)
Keyword pre-filtering was removed. Tools are now offered on **capability alone** and the model
decides when to call each one via native function calling (descriptions are the intent signal).
Each `Tool.should_inject(ctx)` is a pure capability predicate; the keyword `_needs_*(message)`
checks are gone (drive/calendar/gmail/web). Capability = connector active / env enabled / files
attached / URL present / reasoning model.
- **OAuth connectors (Drive + Calendar + Gmail) — EXPOSED as of 2026-06-29:** `ENABLED_CONNECTOR_TYPES = ['google_drive','google_calendar','gmail']` in the frontend; admin can OAuth in and drive real traffic so the session intent latch (`connector_intent.py`) actively fires (Notion/GitHub stay stubbed). Re-enabled for **Phase 0 latch score-logging data collection** (`plans/connector-latch-data-plan.md`). The capability gates (`_drive_gate`/`_cal_full_gate`/`_gmail_full_gate`) + latch withhold each connector's schemas until embedding-cosine intent latches the session (single-winner across connectors); see connector injection bullets below + `llm/tools/connector_intent.py`. **Phase 0 instrumentation:** `_resolve_connector_latches` (`llm/service/stream.py`) scores all three connectors every turn and emits one JSON line per turn via logger `connector_intent.scores` (`evt:"latch_score"` — conv_id/turn/query_emb_present+reason/scores/prior_latch_state/active/argmax/runner_up/margin/decision/why/msg). **Do NOT re-tune `INTENT_THRESHOLDS`/`FLOOR_THRESHOLD` until the real eval sets exist (Phase 1).** Cache-hit turns return before the latch → no log line.
- **Assembly point** (`llm/service/stream.py`): `injected_tools` = registered tools whose
  `should_inject` passes, **name-sorted** for a byte-stable prompt prefix (KV prefix cache →
  near-zero repeat cost). The schema list is routed through `select_tool_schemas(message, schemas)`
  (`llm/tools/registry.py`) — a prefilter switch that is **passthrough today** (`TOOL_PREFILTER_THRESHOLD=32`,
  25 tools) with an empty embedding-prefilter `else` branch reserved for >32 tools. `injected_tools`
  is reconciled to the surviving schema names so `behavioral_rules` stay consistent if the prefilter
  later drops a tool. Behavioral-rules system block is deduped + name-ordered + inserted once.
- **Cost note:** because tools are now almost always present, `tools` is non-empty on most turns,
  so llama-8B is dropped from the fallback chain (it emits tool calls as plain text) and traffic
  leans on the 70B reasoning model. Accepted; a non-issue on the homeserver/Mixtral target.
- Model routing keywords (`_needs_memory_tool`, `intent=="task"` → 70B) are **unchanged** — they
  pick the model, not the tool set, and were out of scope for the de-keyword change.
- Trigger: any message when `file_ids` non-empty → always forces reasoning model (70B); 8B cannot reliably use tool results
- File tools offered when files attached; `_needs_file_tools()` (kept) gates only the retrieval
  global-file fallback in `api/chat/helpers.py`, not tool availability. `list_files`/`search_across_files` fall back to all user's ready files when none attached to conversation (fixed 2026-06-13)

- Tools (25 total): `list_files` · `read_file` (100k cap, capped to 12000 chars in context) · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory` · `web_search` · `fetch_url` · `drive_list_files` · `drive_read_file` · `drive_search` · `calendar_list_events` · `calendar_get_event` · `calendar_search_events` · `calendar_create_event` · `calendar_update_event` · `calendar_delete_event` · `gmail_list_messages` · `gmail_get_message` · `gmail_search_messages`
- **[LIVE 2026-06-29 — `google_drive` exposed in `ENABLED_CONNECTOR_TYPES`]** Drive tool injection (`llm/tools/builtin/drive_tools.py:_drive_gate`): gated on `ctx.drive_active AND ctx.drive_latched` (Q3 Task B — **session intent latch**). The connector being connected is necessary but not sufficient: the three Drive schemas + `_DRIVE_RULES` stay OUT of context until genuine Drive intent latches the session, so the model **cannot** fire `drive_list_files` on a greeting (the "ehllo" over-fire bug — structurally impossible pre-latch, not merely discouraged). The latch is resolved once per turn in `generate_stream` (`llm/service/stream.py:_resolve_connector_latches`): an embedding-cosine score (`llm/tools/connector_intent.py:intent_score("drive", query_emb)`) of the already-computed `query_emb` against a boot-derived intent centroid; `>= max(INTENT_THRESHOLDS["drive"], FLOOR_THRESHOLD)` (0.65 global floor, precision-biased) → latch-then-serve **same turn** + Redis `drive_latched:{conv_id}` (string flag, `ex=3600`, refreshed per latched turn, mirrors `drive_listing:{conv_id}`). **Single-winner across connectors; global `FLOOR_THRESHOLD` (0.65) rejects weak winners that only "won" because all scores were low** (drive/calendar/gmail share a "check my X" structure → high cross-talk; only the top-scoring active+unlatched connector flips, so one request can't latch the others). Sticky per session → one prefix-cache miss on the flip turn, then byte-stable. `query_emb is None` or `USE_REDIS` off → same-turn score only, fail toward fewer tools (never capability-only — that reinstates the bug). `embed_status` (ok/failed/skipped) in the context dict disambiguates *why* query_emb is None: skipped (_is_trivial), failed (embedder down — logged at error level), or never-applicable — so logs answer "embedder down vs skipped" when debugging silent latch failures. NOT a keyword match — the cosine generalizes; phrase list is example sentences for centroid derivation only. Post-latch, `_DRIVE_RULES` (Task A) covers trivial turns; the model picks list/search/read from the schemas. `_drive_list_files`/`_drive_search` are still `is_list_tool` (loop-abort after 1 identical call).
- **[LIVE 2026-06-29 — `google_calendar` exposed in `ENABLED_CONNECTOR_TYPES`]** Calendar tool injection (`_cal_full_gate` → `ctx.calendar_active AND ctx.calendar_latched`, Q3 Task B): all six tools offered when the connector is active **and** the session has latched on calendar intent (centroid `INTENT_THRESHOLDS["calendar"]`=0.60; same `_resolve_connector_latches` single-winner latch + `calendar_latched:{conv_id}` Redis flag as Drive — see Drive bullet). Pre-latch the schemas are absent, so the model can't fire `calendar_list_events`/`calendar_search_events` on a greeting. Write tools (`create`/`update`/`delete`) return `CONFIRM_CALENDAR_PREFIX` sentinel — user must confirm via `POST /api/integrations/calendar/execute` before the Google API call. Execution endpoint dispatches to `llm/tools/calendar.py` impls. **HTTP error handling (all 6 impls, DRY via `_mark_reauth`/`_forbidden`):** `401` → mark `needs_reauth` + `_expired()` message; `403` → `_forbidden()` message (Calendar API not enabled / `calendar.events` scope not granted → "enable the API and reconnect") but **stays `active`** so the tool keeps being offered and the model can relay the fix (do NOT flip to `needs_reauth` on 403 — that hides the tool). A connector error that makes the model retry trips the loop guard, which now forces a tool-free turn to surface the message instead of an empty reply.
- **[LIVE 2026-06-29 — `gmail` exposed in `ENABLED_CONNECTOR_TYPES`]** Gmail tool injection (`_gmail_full_gate` → `ctx.gmail_active AND ctx.gmail_latched`, Q3 Task B): all three tools offered when the connector is active **and** the session has latched on email intent (centroid `INTENT_THRESHOLDS["gmail"]`=0.65, separates cleanly; same single-winner latch + `gmail_latched:{conv_id}` flag). Pre-latch the schemas are absent, so the model can't fire `gmail_list_messages`/`gmail_search_messages` on a greeting. Read-only — no write-confirm sentinel. Impls in `llm/tools/gmail.py`; registration in `llm/tools/builtin/gmail_tools.py`.
- `web_search` injected whenever `WEB_SEARCH_ENABLED=true` (capability only — no keyword match); dispatches to SearXNG (`GET {SEARXNG_URL}/search?format=json`) or Tavily (`POST https://api.tavily.com/search`) based on `WEB_SEARCH_BACKEND`; returns at most 5 results as `[N] title\nurl\nsnippet`; `done` SSE includes `web_searched: bool` (true if any web_search call executed)
- `fetch_url` injected when the message contains `https?://` (capability — nothing to fetch otherwise); fetches full page text via httpx + BeautifulSoup; ephemeral — no File record created; SSRF-hardened (`llm/tools/fetch_url.py`): scheme allowlist, DNS resolved once and connection pinned to that IP (TOCTOU-safe, `sni_hostname` extension preserves SSL cert verification), port allowlist `{80, 443}`, 1 MB streaming byte cap + Content-Length pre-check, Content-Type allowlist; each redirect hop re-validated; `done` SSE includes `url_fetched: bool`
- Guards: same tool **with identical args** repeated past the limit (signature = `(name, json.dumps(args, sort_keys))`; `_MAX_IDENTICAL_CALLS=3`, per-tool override via `Tool.max_identical_calls`) does **not** abort to an empty reply. Instead it appends a "stop calling tools, answer in text" system message, sets `_force_no_tools=True`, and `break`s to one final tool-free model turn — so the model relays any tool error already in context (e.g. a connector 403 → "enable the API and reconnect") to the user. Bounded overall by `MAX_TOOL_ITERATIONS=60` · tool result stored in context capped at 12000 chars (prevents 70B refusal on large repeated reads)
- Tool activity stages: `stage:"tool"` event emitted before each `execute_tool()` call (`"Called: fn(args[:80])"`), `stage:"tool_result"` after call returns (`"fn: result[:100]"`). Accumulated into activity trace and persisted.
- `write_memory` injection gate (`_inject_write_memory`, `llm/tools/builtin/memory_tools.py:27`) = `db AND is_reasoning AND _needs_memory_tool(message)` — i.e. a reasoning turn with **explicit** memory-write intent ("remember"/"memorize" or a write-verb + "memory"; same deterministic keyword signal that routes memory turns to the 70B). It was capability-only (`db AND is_reasoning`), which over-fired: any trivial turn landing on the 70B stored a junk fact + left an **empty reply** (the confirm sentinel pauses the loop) — see BUGS.md (conv `a863dcbf`). Embedding-cosine memory-intent was measured too weak to separate (greetings ~0.58 ≈ real memory statements; "summarize this" 0.75), so it is **not** used. Implicit preferences are still captured by the background memory-extraction pipeline (`summarizer/memory.py`); `write_memory` is only the explicit immediate confirm-card path.
- `ask_user` / `write_memory` / `calendar_create_event` / `calendar_update_event` / `calendar_delete_event` emit SSE + done → pauses loop; amber/green card in UI; `POST /api/memory/write` on user confirm; `POST /api/integrations/calendar/execute` for calendar writes; `ask_user` question persisted as assistant message content so model sees it on next turn
- `append_to_file` for explicit write requests only; `search_in_file` preferred over `read_file` for sections

---

### Token Buffering (`llm/service/stream.py`)
- Tokens accumulated in `_token_buffer` per `call_stream` call
- If response contains tool calls → discard buffered tokens (prevent model from generating preamble text before tool execution, then duplicating it after)
- If no tool calls → flush buffer as normal SSE `content` events

---

## Memory System
Injection order: system → GRAPH CONTEXT → GRAPH FACTS → USER STATE → ACTIVE GOALS → RECENT INSIGHTS → PROJECT → RELEVANT CONTEXT → EARLIER IN THIS CONVERSATION → LAST SESSION → history → FILE CONTEXT → user message

- Triggers: memory update >3000 tok OR every 10 asst msgs; history compression + project summary update >4000 tok OR every 15 total msgs (all_count > 10); auto-title after 2nd msg via `asyncio.create_task`
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races
- Compaction: LLM-driven dedup via `compact_memory()`; creates `UserMemoryVersion` snapshot; queued via ARQ or daily cron at 3 AM UTC; sets Redis lock `compact:running:{user_id}` (EX 300s) — graph extraction skips while held
- Preference extraction: `extract_preferences_job` every 50 asst msgs; writes `[PREFERENCES]` to `UserMemory.content`; Redis lock `pref_extract:running:{user_id}` EX 300s
- Behavior tracking: `update_behavior_profile_job` per reply; increments query_type/topic/tools/models counters in `UserBehaviorProfile.profile` JSONB; no LLM; feeds `generate_user_insight()`
- Cross-conversation insights (`[RECENT INSIGHTS]` block): `_build_stream_context()` queries top-3 `UserInsight` rows (30-day window); injected between `[ACTIVE GOALS]` and `[PROJECT STATE]` in system prompt; budget tier 2 (same as PROJECT STATE); emits `stage:"insights"` in activity trace
- Context budget: drops lowest-tier sources when tokens exceed `context_window - max_output_tokens - 10%`; re-applied per tool iteration
- Salience: bumped on context load via `compute_salience()`, decayed 0.95/cycle during compaction; cleared when <0.3
- Conflict resolver: `MemoryConflict` stores fact_a/b/type/resolution/expires_at; +7d on scan; expired unresolved auto-resolved `keep_a`; resolve via `POST /memory/conflicts/{id}/resolve`
- Per-fact salience: `fact_saliences` JSONB maps fact→score; time-based decay `0.95^(hours/24)` before top-20; bumped per-access; <0.05 pruned; low-salience dropped first by budget allocator
- Retrieval re-ranking: `final_score * (1 + memory_salience * 0.05)` after retrieval

---

## Files & Knowledge
- Upload: SHA256 while streaming → dedup `(user_id, hash)` → ARQ job or inline fallback
- Formats: PDF · DOCX (+tables after paragraphs) · XLSX/XLS · image (CPU PaddleOCR, gated by IMAGE_OCR_ENABLED) · text/code/markdown
- Chunks: 1600 chars, 200 overlap, sentence-aligned tail
- Chunk quality states: `upload_status` values are `uploaded|processing|ready|partial|failed|error`; `partial` = some chunks embedded, some failed; `File` has `chunk_total`, `chunk_embedded`, `embed_fail_count`; status reset and counts cleared on file edit
- Scanned-PDF OCR: pypdf blank + IMAGE_OCR_ENABLED → pypdfium2 render → PaddleOCR extract → joined text; _PDF_OCR_MAX_PAGES=20; gate off → empty text, 0 chunks (no error)
- Retrieval: vector + BM25 parallel → RRF (k=60) or weighted fusion; fallback to pure vector
- Adaptive policy: `classify_query(msg)` in `router.py` returns `factual|relational|temporal|broad`; mapped in `retriever/policy.py` to fusion_mode/alpha/k values (factual=weighted 0.7, relational=RRF, temporal=RRF low-k, broad=weighted 0.3); applied per-query in `_build_stream_context()`; logged with query_type + params; activity trace detail includes top-3 dense scores (`· scores: 0.82 | 0.71 | 0.65`); also emitted in `done` SSE event as `query_type` + `src_count` (number of retrieved provenance chunks)
- **Reasoning Loop / intent (Dim 3):** `_build_stream_context()` calls `classify_intent_hybrid()` → tunes a **copy** of the policy dict (exploration → `top_k`+4, `k_dense`≥20; question → `top_k`−1; task → unchanged — never mutates shared `POLICY_MAP`); sets `ctx["intent"]` + `ctx["retrieval_top_k"]`; appends an `Intent: <x>` row to the activity trace. `intent` threads into `generate_stream(intent=…)` where `intent=="task"` adds a `task-intent` model branch preferring the reasoning model (tool-eager; 8B emits tool calls as plain text). `done` SSE now also carries: `intent`, `grounding`, `activity`.
- **Grounding confidence (Dim 3):** `_compute_grounding(provenance, top_k)` in `api/chat/stream.py` → `{level: high/medium/low/none, score: int|null, sources:[…]}`. Uses `dense_score` (cosine sim, 0–1, fusion-mode-independent) — **NOT** `final_score`, which is not comparable across weighted (~0–1) vs RRF (~0.016) fusion. `score = round(100*(0.7*avg_top_dense + 0.3*coverage))`; empty provenance → `level:"none"`. Tested in `tests/test_reasoning_loop.py` (11 tests, no NIM). **Persistence:** `_build_provenance(ctx)` + `_build_render_meta(ctx, provenance)` run once *before* the assistant-message persist (done branch) → `render_meta` stored on the message and reused for the `done` event (no double-compute). `GET messages` returns `grounding`/`query_type`/`src_count` from `render_meta`, so the badge survives refetch/reload/history (not live-only).
- **Reasoning trace (Dim 3):** the `activity[]` trace (already built in `_build_stream_context` + appended live in `generate_stream`, persisted as `messages.activity_trace`) is now also emitted in the `done` SSE event so the frontend renders it without a refetch. Pipeline-level trace, **not** model chain-of-thought.
- Status SSE: polls `db.refresh` + Redis `proc_progress:{file_id}` every 0.8s → terminates on ready/error
- `file_service`: save_version before every mutation; `_fuzzy_replace`: exact → `\r\n` norm → stripped edges

---

## Admin / Cost
- Cost cap: rolling window (`cost_window_days`, default 30, null=all-time) → 402 on exceed; label in error e.g. `$4.23 / $5.00 30d`
- Audit actions: `user.active.enabled/disabled` · `user.cost_limit.set/removed` · `env.updated` · `env.reloaded` (JSONB with prev+new values)
- Self-disable blocked; `is_active` checked on every `get_current_user`
- API key: JWT first, DB key fallback in `auth/security.py`; stored as SHA-256 hex (`hash_api_key()`), hashed on every lookup — plaintext never persisted
- Model pricing (`config.py`): llama $0.10/$0.10 · coder $0.20/$0.60 · reasoning $0.77/$0.77 per 1M tokens
- Web search config: `WEB_SEARCH_ENABLED` (bool, default false) · `WEB_SEARCH_BACKEND` ("searxng"|"tavily", default "searxng") · `SEARXNG_URL` (default http://searxng:8080) · `TAVILY_API_KEY` (str) · `IMAGE_OCR_ENABLED` (bool, default false) — CPU PaddleOCR for images + scanned-PDF fallback
- Voice/STT config: `VOICE_ENABLED` (bool, default false) · `ASR_BACKEND` (str, default "stub") · `ASR_MODEL` (str, default "base.en") · `ASR_LANGUAGE` (str, default "")

---

## Non-obvious Invariants
- pgBouncer transaction mode → `prepared_statement_cache_size=0` required (`core/db.py`)
- Cache: early check before context build; v2 key = msg+model+history[-4]+sysprompt; bypassed on image_b64 / model_params / ConversationFile
- ARQ: api enqueues → arq-worker consumes; inline fallback when pool unavailable
- SHA256 dedup: returns existing file + `duplicate: true` — no re-upload
- Sync file I/O + CPU parsing wrapped in `asyncio.to_thread()` (tools.py, file_service.py, processor.py)
- Rate limiter reuses `request.state.current_user` to skip JWT re-decode
- Auth uses `bcrypt` directly (no passlib) — `hash_password()` + `verify_password()` in `auth/security.py`; existing `$2b$` hashes remain compatible
- API keys use SHA-256 (`hash_api_key()` in `auth/security.py`) — not bcrypt, since keys are already high-entropy; migration 039 NULLed all pre-existing plaintext keys
- Dotenv admin: `/admin/env` masks sensitive keys; PUT writes `.env` + updates running config; `POST /admin/env/reload` does `importlib.reload(config)`
- **`LLM_BACKEND` switch (`nim`|`homeserver`, default `nim`)** — single flag in `config.py` that flips the app between the NIM test backend and the local llama.cpp/Mixtral stack. A gated block (run **before** the startup guards, so `importlib.reload` re-applies it) repoints `NIM_URL`/`NIM_EMBEDDING_URL`, collapses `MODELS` to one Mixtral alias, sets `CONTEXT_WINDOWS`/`DEFAULT_CONTEXT_WINDOW=32768`, swaps `MODEL_EMBEDDING`→`bge-large-en-v1.5` (1024-d, no re-embed), and relaxes the `NVIDIA_API_KEY` guard (`LLM_BACKEND != "homeserver"`). Toggleable live via `/admin/env` PUT + reload — **no restart**.
  - ⚑ **Runtime reload only propagates to call-time `config.X` reads.** The hot path was converted from `from config import NIM_URL` (frozen at import) to `import config` + `config.NIM_URL` in `llm/nim.py`, `llm/embeddings.py`, `llm/router.py`, `llm/service/stream.py`, `api/system.py`. **Do not regress these to `from config import` or the live toggle silently stops working.**
  - Stale NIM model ids from still-frozen callers (summarizers, `helpers.py`, etc.) are harmless: llama.cpp ignores the `model` field in single-model mode, and `get_context_limit()` returns `DEFAULT_CONTEXT_WINDOW` (32k) for any id not in the homeserver `CONTEXT_WINDOWS`. `MODEL_RATE_LIMITS`/`MODEL_PRICING` stay NIM-keyed (cosmetic; router is telemetry-only in homeserver mode).
  - Auth header (`nim.py`/`embeddings.py`) is sent only when `config.NVIDIA_API_KEY` is set (avoids `Bearer None` to the keyless LAN server).
  - ⚑ **Connector-intent latch centroids + thresholds are embedder-specific — re-tune on the bge swap.** As of 2026-06-29 the Google three are exposed and the latch fires live (Phase 0 data collection). `llm/tools/connector_intent.py` derives a per-connector centroid (drive/calendar/gmail) at boot from `INTENT_PHRASES`; those auto-regenerate correctly under bge. BUT `INTENT_THRESHOLDS` (drive 0.60 / calendar 0.60 / gmail 0.65) and `FLOOR_THRESHOLD` (0.65) are tuned to nv-embedqa-e5-v5's score distribution and will be **wrong** for `bge-large-en-v1.5`. On the homeserver port: re-run `tests/{drive,calendar,gmail}_intent_eval.jsonl` under bge and re-set all three per-connector thresholds + floor threshold (+ recheck cross-talk). Symptom if skipped: connector schemas latch too early/late silently. (Q3 Task B.)
- **`MEMORY_LOCK_BACKEND` switch (`pg`|`redis`, default `pg`)** — inert switch for #21 Horizontal Scaling, same pattern as `LLM_BACKEND`. `core/locks.py` provides `user_write_lock(db, user_id)` async context manager that dispatches on `config.MEMORY_LOCK_BACKEND`. `pg` → `SELECT pg_advisory_xact_lock(:key)` (current behavior, zero change). `redis` → `SET lock:mem:{user_id} <uuid> NX EX <TTL>` with spin/backoff + Lua compare-del release, `TimeoutError` on acquire failure. Defaults: TTL 30s, wait 5s. Config: `MEMORY_LOCK_TTL` (int), `MEMORY_LOCK_WAIT` (int). Toggleable live via `/admin/env/reload`. 5 call-sites replaced to use the abstraction: `memory.py:28/119`, `preferences.py:75`, `project.py:22`, `compact.py:139`. Tested in `tests/test_mem_lock.py` (9 tests, AsyncMock, no Redis).
- `.env` merge script in root CLAUDE.md — adds missing keys from `.env.example` as commented-out
- Debug mode: `retriever.retrieve()` / `retrieve_from_files(debug=True)` returns `(chunks, debug_info)` tuple; `/search?debug=true` returns `{"results": [...], "debug": [...]}`
- Eval harness: `tests/retrieval/test_hybrid_eval.py` — 26 tests, mock DB (AsyncMock), no NIM deps; run with `pytest tests/retrieval/ -v`
- Neo4j indexes created on startup: unique constraint `(user_id, name)`, fulltext `entity_name_ft` on `e.name`, range index `entity_user_id` on `e.user_id`; also creates `canvas_user_id` index on `CanvasNode.user_id` (harmless dead code — canvas removed, `core/neo4j_client.py` not touched); writes use UNWIND batch (2 round-trips regardless of entity/rel count); graph query results cached in Redis (key `graph:{user_id}:{sha256[:32]}`, TTL 60s, USE_REDIS gated); cache busted on every entity write (`_cache_del_user`)
- NIM retry: `MAX_RETRIES=3` (4 total); exponential backoff with jitter `min(30, 2**attempt) * (0.75 + 0.5*random)` — attempt 0≈1s, 1≈2s, 2≈4s, 3≈8s
- Embed retry (`llm/embeddings.py:embed`): `_MAX_ATTEMPTS=4`; retries **5xx + transport/timeout** with backoff 0.5/1/2s, fails fast on 4xx. Added 2026-06-30 because the NIM embedder's intermittent 500s nulled `query_emb` and silently disabled the connector latch (`embed_status="failed"`); cut the embed-fail rate from ~78% to ~0% in the latch data run. Latency paid only on a failing turn
- Circuit breaker: _THRESHOLD=5, _COOLDOWN=90s; Redis-persisted `cb:open:{model}` EX 90; restored on startup via `restore_circuit_state()`; pre-tripped at startup by `probe_models_on_startup()` for any model returning non-200
- Prometheus: multiprocess mode active when `PROMETHEUS_MULTIPROC_DIR` set — `export_metrics()` uses `MultiProcessCollector(CollectorRegistry())`; new counters: `stream_interruptions_total`, `all_models_failed_total`, `arq_job_failed_total{job_type}`
- Summarizer imports: `api/chat/stream.py` imports `compress_history`, `update_memory`, `update_project_summary` from `llm.summarizer.*` — missing these causes `NameError` at runtime (caught by except handler, skips memory update)

### External Integrations (since 2026-06-12)
- `ExternalSource` model: `id`, `user_id`, `connector_type` (google_drive|google_calendar|gmail|notion|github), `display_name`, `resource_id`, `credentials` (JSONB, Fernet-encrypted), `status` (pending|active|error|needs_reauth|paused), `error`, `last_sync_at`, `created_at`
- `core/encryption.py`: `encrypt_token()`, `decrypt_token()`, `fernet_ready()` — uses `cryptography.fernet.Fernet`; returns 503 on all creation/oauth endpoints when key missing
- `services/integrations/` package: `AbstractConnector` ABC (TypedDicts: `OAuthTokens`, `ConnectorCredentials`, `SyncedChunk`) + `registry.py` (auto-register via `@register` decorator) + per-provider: `google_drive.py`, `google_calendar.py`, `gmail.py`, `notion.py`, `github.py`
- API routes (`/api/integrations`): `GET/POST /integrations`, `GET/PATCH/DELETE /integrations/{id}`, `POST /integrations/{id}/sync`, `GET /integrations/oauth/start`, `GET /integrations/oauth/callback`
- OAuth callback (`/api/integrations/oauth/callback`) has **no JWT** authorization — identity from Redis state `intg:state:{uuid4}` → `{user_id, connector_type}`, TTL 600s
- New config vars: `INTEGRATION_SECRET` (Fernet key, 44-char base64url), `INTEGRATION_REDIRECT_BASE` (default `http://localhost:8000`), `GOOGLE_CLIENT_ID/SECRET`, `NOTION_CLIENT_ID/SECRET`, `GITHUB_CLIENT_ID/SECRET` — all nullable `os.getenv(key, "")`
- ARQ job `sync_external_source_job(ctx, *, source_id)`: retries with `_RETRY_DELAYS=[5,30,120]`, 401/403 → `needs_reauth` no retry, final failure → `ARQ_JOB_FAILED` counter + `status="error"`; decrypts credentials, refreshes if expired (fast-fails to `needs_reauth` if expired AND no refresh_token), sets `last_sync_at` + `status="active"`. **Does NOT ingest content** — `iter_chunks()`/`StorageManager.save_text()`/`process_file_job` were removed when Drive moved to on-demand tools (`llm/tools/drive.py`). `iter_chunks()` is defined on connectors but unused. Drive/Calendar content is fetched live per request, never synced to `File`/pgvector. Connector `iter_chunks` impls retained for a possible future sync but are dead code today.
- Google OAuth auth URL includes `prompt=consent` to guarantee refresh_token on every authorization (without it Google only returns refresh_token on first auth)
- Scheduler: `run_integration_sync()` enqueues sync for all active sources every 6h (cron `0 */6 * * *`, id `__integration_sync__`)
- Migration 042: created `external_sources` table with unique index `(user_id, connector_type, resource_id)` and index on `user_id`

---

## HANDOFF Protocol — Quick Reference

- **Role:** backend worker. Do not plan or delegate.
- **Scope:** `backend/` files only. Cross-dir tasks → put in `HANDOFF.md` section, pass file.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## backdir`, execute tasks, fill `### Recorded` (endpoint shapes, env vars, SSE events, DB columns), update this file, append History, `mv HANDOFF.md ../frontend/HANDOFF.md`.
- **Recorded facts:** write terse, precise — next agent has no backend context.

> Full protocol: `../HANDOFF_PROTOCOL.md`

---

## Verification & Test Tiers (since 2026-06-22)

`pytest.ini` registers four markers; gating is automatic in `tests/conftest.py` — an opt-in
tier with its prerequisite unmet **skips**, so a plain `pytest` stays green on a laptop.

| Tier | Marker | Needs | Run |
|------|--------|-------|-----|
| Unit | `unit` (default) | nothing | `pytest -m "not infra and not live_nim and not optional"` |
| Infra | `infra` | Postgres+pgvector / Redis / Neo4j | `RUN_INFRA=1 pytest -m infra` |
| Live E2E | `live_nim` | running stack + live model | `RUN_LIVE_NIM=1 VERIFY_BASE_URL=… pytest -m live_nim` |
| Optional | `optional` | per-feature creds/flags | `RUN_LIVE_NIM=1 VERIFY_BASE_URL=… pytest -m optional` |

- `tests/conftest.py` — shared env defaults + HTTP fixtures (`client`, `user_token`/`admin_token`,
  `user_headers`/`admin_headers`, `sse_post`). `VERIFY_BASE_URL` default `http://localhost:8000`;
  seeded creds via `VERIFY_USER`/`VERIFY_USER_PW` (default `user`/`user-secret`).
- `tests/live/` — **HTTP-driven** against a real running stack (the trustworthy E2E path; exercises
  real NIM/DB/Redis/Neo4j). Covers chat SSE + `done` contract, grounding persistence, non-stream +
  model override + cache-bypass, **RAG tool loop**, files CRUD/dedup, endpoint sweep, admin + secret
  masking, auth lifecycle, health/metrics/401. 42 passed / 3 skipped on 2026-06-22.
- `tests/integration/` — `infra` tier: migration integrity (single head, ≥47 revs, applied==head),
  pgvector + `vector(1024)` invariant + core tables, Redis set/get/TTL/`SET NX`, Neo4j roundtrip +
  `entity_name_ft`. Auto-skips services unreachable from host.
- `scripts/smoke.sh <base_url>` — post-deploy smoke (health→login→upload→one live `/chat/stream`→
  metrics→cleanup), exits non-zero on failure.
- Full runbook + launch checklist: `tests/VERIFICATION_LAUNCH.md`. Non-stream `/chat` returns
  `{success, data:{model,response}, meta}`; `cache_hit` is **stream-only** (`done` event) and `false`
  on the stream path by design.

### `tests/live/test_tools_integrations.py` — full tool + integration sweep (2026-06-22)

Drives **every agent-tool family** through a real model and the set-up OAuth connectors.
**13 passed / 1 skipped** on 2026-06-22 (gmail skip = not connected). Calendar passed once the
Calendar API + `calendar.events` scope were enabled in Google Cloud and the connector reconnected.

- **Assertion mechanism** (three ways): the `tool_call` SSE event names the tool; `GET
  /tool-calls?conversation_id=` shows the `ToolCallLog` row persisted; flag-bearing tools set
  their `done` flag (`web_searched` / `url_fetched`). Helpers: `_assert_completed` (fired +
  `done` + persisted) for clean-finish tools; `_assert_fired` (tool_call only — no `done`
  required) for paths that legitimately end in an `error` event (loop-guard abort, write tools);
  `_skip_if_connector_error` turns a live connector API error into a skip-with-reason.
- **Covered, firm:** `web_search` (+`web_searched`, +negative gating test), `fetch_url`
  (+`url_fetched`), `list_files`, file-search family (`search_across_files`/`search_in_file`/
  `read_file` — model's choice with one file), `query_graph`, `create_file`, `ask_user`
  (+`ask_user` SSE pause), `write_memory` (+`confirm_write_memory` sentinel; never executed),
  Drive `drive_list_files`/`drive_search` (admin), calendar `calendar_create_event`
  (+`confirm_calendar_write` sentinel; never executed).
- **Gating to fire a tool deterministically:** strongly-steering prompts ("Use the X tool to…").
  Web search also needs `WEB_SEARCH_ENABLED=true` + searxng up (profile `web-search`). Drive/
  calendar tests use **admin** headers (connectors are connected under admin, not user) and
  self-skip if the connector isn't `active`.
- **Calendar (resolved 2026-06-22):** previously 403'd because the Calendar API/`calendar.events`
  scope weren't enabled in Google Cloud. After enabling both + reconnecting the connector, calendar
  list/create verify live (real events returned). The 403 hardening stays as defense: tool returns
  `_forbidden()` + keeps the connector `active`, and the loop guard forces a tool-free final turn —
  so any future connector error surfaces as an actionable reply, never an empty one (the test still
  asserts that graceful path before skipping if a 403 ever recurs).
