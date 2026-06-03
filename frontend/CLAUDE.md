# Frontend Reference

## Stack
- React + Vite; `vite.config.js` proxies `/api` → `localhost:8000`
- `src/App.jsx` — login form, JWT in localStorage as `nim_token`
- `src/components/Chat/index.jsx` — orchestrator; uses `useStreamChat` hook for SSE, `closeAllExcept` helper, wraps panels in `<PanelPropsCtx.Provider>` with all hook state as single object
- `src/components/Chat/PanelPropsContext.js` — React context eliminating prop drilling; panels consume via `usePanelProps()`
- `src/lib/chatStyles.js` — shared style objects; `LAYERS` constant for z-indices, `panelBase` for all slide-in panels
- `src/hooks/` — 13 hooks: useConversations, useMemory, useFiles, useModelParams, useSettings, useToolLogs, useUsage, useAdmin, useInsights, useSearch, useScheduledPrompts, useGoals, useStreamChat
- `src/components/Chat/*/index.jsx` — 14 sub-components: Sidebar, MessageList, ModelToolbar, SettingsModal, FilesPanel, FileViewer, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel, SearchPanel, AutomationsPanel, GoalsPanel
- **All fetch calls must use `/api/` prefix** — bare paths bypass proxy and 404 silently
- **JWT flow:** login → `POST /api/auth/token` → store token as `nim_token` in localStorage → `Authorization: Bearer` on all fetch calls

---

## Chat/index.jsx — Key Features
- **SSE streaming extracted to `useStreamChat` hook** — `Chat/index.jsx` calls `const { send, buildBody } = useStreamChat({ token, conv, modelParams, ws, mem, insights, onLogout })`. The hook manages all streaming state internally.
- Streaming: raw `<p>` + blinking cursor → done → `<ReactMarkdown>` in `.md-body`
- Per-bubble: `{totalTokens} tok · $x.xxxxx · [query_type] · N src`; live from SSE "done" (`query_type`, `src_count`, `provenance[]` fields); `[query_type]` = factual/relational/temporal/broad; `· N src` badge green ≥3, amber 1–2, hidden if 0
- **Conversation search** — debounced 300ms; `GET /api/conversations?q=`; clears on empty
- **Conversation export** — ⬇ per conv; `GET /api/conversations/{id}/export?format=markdown`
- **Invite panel** (admin) — ⚡ button; load `GET /api/auth/invites`; generate `POST /api/auth/invite`; click to copy
- **Admin endpoints** (API-only, no frontend panel): `/api/admin/users`, `/api/admin/users/{id}/cost-limit`, `/api/admin/audit-log`
- **$ Usage panel** — slide-in; aggregate `GET /api/usage`; **⬇ Export All Data** button at bottom → `GET /api/export/full` (bearer token header) → downloads `export.zip` (conversations · files · memory · graph); token passed as prop from `Chat.jsx`
- **Compare mode** — same streaming/done split per model card
- **Automations panel** (ROADMAP #12) — ⏱ Auto header button; slide-in; `useScheduledPrompts.js`; CRUD for scheduled prompts via `/api/scheduled-prompts`; create/edit form with preset aliases (daily/weekly/monthly) or custom cron, optional model_override; per-row: active toggle (`PATCH is_active`) · ▶ Run (`POST /run`) · ▼ Runs (expandable run history from `GET /id/runs`) · Edit · 🗑 delete; form overlays panel with zIndex:2
- **Goals panel** (ROADMAP #13) — 🎯 Goals header button; slide-in; `useGoals.js`; CRUD via `/api/goals`; status filter pills (all/active/paused/completed); per-card: StatusBadge · linked conv count · toggle active↔paused · 🔗 Link conv (if `activeConvId` set + goal active, `POST /goals/{id}/link/{convId}`, disabled if already linked) · Edit · 🗑 delete; create/edit form overlay (title, description, status dropdown)
- **⬡ Canvas button** — opens `/canvas/index.html` in a new tab; styled red (`color:RED, borderColor:RED`); placed in header before Logout; canvas checks `nim_token` in localStorage and redirects to `/` if missing

## Files Panel
- 📎 header button; amber + count when files attached; 2 tabs: Library / Attached
- Library: status badge · inline rename · 👁 view · ⬇ download · +/✓ attach · 🗑 delete
- Processing: SSE per file (not polling); `AbortController` in `statusStreamsRef`

## File Viewer Modal
- 3 tabs: **View** (`<pre>` + download) · **Edit** (textarea → `PUT /api/files/{id}/content`) · **Versions** (list + restore)
- Closes on overlay click or ✕

## Tool Log Panel
- 🔧 button → slide-in; `GET /api/tool-calls?conversation_id=&limit=100`
- Filter: This conversation / All; per-row: tool name (purple), timestamp, args, result preview
- `conversation_id` query param is `encodeURIComponent`-encoded in `useToolLogs.js`

## Panels & Cards
- **Last session banner**: muted line `✦ Last session: "…" — X ago` above first AI bubble on SSE `done.last_session`; `lastSession` state in `useConversations.js`; auto-dismisses after 8s or on next send
- **Proactive suggestion**: indigo card below chat feed on `{type:"proactive"}` SSE; ✕ dismiss; clears on next send
- **Insights**: 💡 button; unread badge; `GET /api/insights`; click → mark read; 🗑 delete; indigo dot for unread
- **ask_user**: amber card "NEEDS CLARIFICATION" on `{type:"ask_user"}` SSE; user reply resumes with full context
- **confirm_write_memory**: green card "MEMORY SUGGESTION" on `{type:"confirm_write_memory", fact}` SSE; Accept → `POST /api/memory/write {fact}`, Dismiss → null; clears on next send
- **Memory panel**: tabs View / Edit / History / Graph / Conflicts — View tab renders per-fact cards from `memData.facts[]` (each card: content + salience score bar (4px, green ≥0.7 / amber ≥0.4 / grey below) with % label to right + `Last accessed: X ago` / `Never accessed` timestamp from `last_used_at`); falls back to splitting `content` by newline if `facts`/sections missing; PROJECT STATE section; Graph tab: `GET /api/graph/stats` → `{available, entities, relations}`; auto-refreshes 2s after each AI reply if tab open
- **Conflicts tab** (ROADMAP #5): `GET /api/memory/conflicts` on tab open → list; tab label shows count when > 0; per-card: `fact_a` + `fact_b` side by side, type badge (red=contradiction, yellow=duplicate, grey=ambiguous), four resolve buttons (Keep A / Keep B / Merge / Discard Both) → `POST /api/memory/conflicts/{id}/resolve` `{ strategy: "keep_a"|"keep_b"|"merge"|"discard_both" }` → removes card on success; empty state: "No conflicts"; state in `useMemory.js` (`conflicts`, `conflictsLoading`, `loadConflicts`, `resolveConflict`)
- **Graph tab** (ROADMAP #8): interactive SVG circle-layout graph; tab open calls `loadGraphStats()` + `loadGraphSample(limit, entityType)`; controls: entity_type text filter + limit number input (default 50, max 200) + refresh; nodes = circles (6px), edges = lines; click node → highlights its edges + neighbors, shows relation list below (`source —[relation]→ target`); labels shown for selected/neighbors/graphs ≤12 nodes; state in `useInsights.js` (`graphSample`, `graphSampleLoading`, `loadGraphSample`); endpoint: `GET /api/graph/sample?limit=&entity_type=`
- **Re-embed button**: ↺ Re-embed All in Invite panel admin section → `POST /api/admin/re-embed`

## Unified Search Panel (ROADMAP #7)
- 🔍 header button → slide-in `SearchPanel.jsx`; state in `useSearch.js`
- Input debounced 300ms → `GET /api/search?q=&scope=all|files|conversations|memory|graph`
- Scope pills: All / Files / Conversations / Memory / Graph
- Results grouped by source; source label colors: files=amber, conversations=indigo, memory=green, graph=sky
- Score shown as monospace float right of title; snippet clamped to 2 lines
- Clicking a `conversations` result calls `selectConv(id)` and closes the panel
- Response shape: `{ query, scope, results: [{ source, score, title, snippet, id }] }`

## Model Control Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B · ⊞ Compare · ⚙ params (temp, max_tokens, top_p with per-slider enable)
- ⚙ settings modal: system prompt · model lock (`PATCH /api/conversations/{id}`)
- Ctx button: **OBSOLETE — memory is always-on; this toggle should be removed** · sidebar shows 🔒 when model locked

## JARVIS Canvas (Stage 5)
- Static bundle at `frontend/public/canvas/` — served by nginx/Vite at `/canvas/`
- Entry: `index.html` loads React 18 + ReactFlow 11 + Babel standalone (no build step)
- Script load order: `styles.js` → `data.js` → `canvas-live.js` → `canvas-sse.js` → Babel JSX components
- `canvas-live.js` — auth gate (`nim_token`), parallel fetch of all API nodes, patches `INITIAL_NODES` before React mounts; calls `/api/system/hardware`, `/api/memory`, `/api/files`, `/api/usage`, `/api/tool-calls?limit=50`, `/api/conversations`
- `canvas-sse.js` — intercepts `NIM_CANVAS_CB` assignment; replaces `onDemoSend` with real `POST /api/chat/stream`; maps SSE events → node animations + session output streaming; reads `NIM_CANVAS_LAST_FILE_IDS` for File→Session wire (`file_ids` field)
- `effects.css` — CRT overlay styles at `frontend/public/effects.css`; `index.html` references as `../effects.css`
- `cpu-schematic.svg` wallpaper at `frontend/public/cpu-schematic.svg`; referenced as `../cpu-schematic.svg`
- All API calls use `/api/` prefix — Vite proxy (dev) and nginx (prod) strip it before forwarding to backend

### Canvas — JARVIS Global AI
- `GET /api/canvas/global` — returns-or-creates the JARVIS conversation (`title="JARVIS"`) for the user; called by `canvas-live.js` at boot; result stored as `window.NIM_CANVAS_GLOBAL_CONV_ID`
- InputNode has no session dropdown — sends to global conv by default via `NIM_CANVAS_GLOBAL_CONV_ID` fallback in `buildBody()`; shows `JARVIS // GLOBAL` static label
- SessionNode is simplified — no session picker, no LIST button; shows `GLOBAL SESSION / JARVIS // PERSISTENT` for the primary node; AI-created session nodes show `AI SESSION / <uuid prefix>`
- AI tool `create_conversation` creates a real Postgres record, then AI follows with `create_canvas_node` to visualize; `canvas_update` SSE triggers `_patch` to show new nodes
- All messages from Input node always route to JARVIS global conversation; `NIM_CANVAS_LAST_SESSION_ID` can override (used by AI-created session nodes in future)

### Canvas — Backend Bridge (Neo4j ↔ React Flow)
- `GET /api/canvas/graph` → `{"nodes": [...], "wires": [...]}` — fetched by `canvas-live.js` at boot and by `canvas-sse.js` on `canvas_update` events
- AI canvas nodes use `id: "ai-{uuid}"` prefix to distinguish from the 8 static demo nodes (`input`, `session`, etc.)
- AI wires use `id: "ai-wire-{src_uuid}__{dst_uuid}"` (double underscore separates UUIDs)
- `neoToRF(n, idx)` — defined at module scope in `Canvas.jsx` AND in `canvas-live.js`; maps `node_type` → React Flow `type` via `_NEO_TYPE_MAP`; unknown types fall back to `placeholder`
- `patchCanvas({nodes, wires})` — `useCallback` in `Canvas.jsx`; replaces all `ai-*` nodes/edges with fresh data from the API; exposed on `window.NIM_CANVAS_CB._patch`
- `aiWireMapRef` — `useRef({})` in `Canvas.jsx`; maps `edgeId → {src_id, dst_id}`; populated by `patchCanvas` and `onConnect`; used by `handleEdgesChange` for backend DELETE lookups
- `handleEdgesChange` — wraps built-in `onEdgesChange`; on `type:"remove"` for `ai-wire-*` edges, fires `DELETE /api/canvas/wire` (fire-and-forget)
- `onConnect` — after adding edge to React Flow state, if either endpoint is `ai-*`, fires `POST /api/canvas/wire` with `{src_id, dst_id, src_port, dst_port, relation:"connected"}`
- `canvas-sse.js` `canvas_update` case — re-fetches `/api/canvas/graph`, calls `_patch`; also pulses Logs node
- AI wire edges rendered in green (`rgba(61,255,110,0.6)`) to distinguish from demo wires (`#555555`)

### Canvas — Smart Handle Routing
- `nodes.jsx` `AllHandles()` exposes 8 handles per node: `s-top` `s-right` `s-bot` `s-left` (source) + mirrored `t-*` targets
- `pickHandles(srcId, tgtId, nodes, edges)` in `Canvas.jsx` — scores all 16 src×tgt combos; score = `dist(srcHandle→tgtCenter) + dist(tgtHandle→srcCenter) + occupancy×80px`; lowest score wins
- `SMART_INITIAL_EDGES` — pre-stamps handles on `D.INITIAL_EDGES` at module load before React mounts
- `onConnect` — calls `pickHandles` only when user drops on node body (no explicit handle); handle-drag always wins
- Memory branch edges — `pickHandles` called with branch positions pre-computed so all 3 branches fan to different ports on Memory node

### Canvas — Real-time Drag Re-routing
- `nodesRef` — `React.useRef` mirror of `nodes` state; synced via `useEffect([nodes])`; avoids stale closure in RAF callback
- `dragRafRef` — RAF handle; cancelled + rescheduled on each `onNodeDrag` so only the latest drag position is processed (≤60fps)
- On each RAF fire: build `patchedNodes` with dragged node at cursor position → `pickHandles` for each connected edge (edge excluded from its own occupancy count) → `setEdges` only if handles changed

## Markdown CSS
Scoped to `.md-body` via `<style>` tag. Covers: p · h1-h4 · code/pre · ul/ol/li · blockquote · table · a · strong · em · hr

## Conventions & Known Fixes

### Component Structure
- **All components use `ComponentName/index.jsx` pattern** — no flat `.jsx` files under `components/`. Imports must omit file extension (Vite resolves to `index.jsx` automatically).
- **Panels consume `usePanelProps()` from `PanelPropsContext.js`** — no prop destructuring in panel function signatures. Each panel destructures its slice: `const { foo, bar } = p.mem`, `const { baz } = p.conv`, etc.
- **New hook state belongs in context provider** — add to the ctx object in `Chat/index.jsx`, not as new props on every panel.
- **Message roles:** AI messages use `role: 'ai'` (not `'assistant'`) — `MessageList.jsx` conditions must match `'ai'`
- **`queryType` / `srcCount` badges** render only on `role === 'ai'` + `!streaming`
- **`deleteInsight`** captures `wasUnread` before the `await` to avoid stale closure
- **`attachedIds`** in `useFiles.js` is a `useMemo` — do not revert to inline `new Set()`
- **`closeAllExcept(...keep)`** — single helper in `Chat/index.jsx` for panel close logic. Adding a panel requires zero handler edits.
- **Derived memory values**, **derived search values**, **derived file values** and all hook return values are collected into a single `ctx` object in `Chat/index.jsx` and passed via `<PanelPropsCtx.Provider>`. Add any new derived value to the `ctx` object — never thread it as a separate prop.
- **`LAYERS` constant** in `chatStyles.js` centralizes all z-indices. Use `LAYERS.panel`, `LAYERS.viewer`, `LAYERS.settingsModal`, `LAYERS.wsModal` — never raw z-index values.
- **`panelBase`** in `chatStyles.js` provides shared slide-in panel styles. All 6 side panels use `{...panelBase, width, maxWidth}` with overrides only for dimension/color differences.

---

## HANDOFF Protocol — Quick Reference

- **Role:** frontend worker. Do not plan or delegate.
- **Scope:** `frontend/` files only. Cross-dir → `HANDOFF.md` section + pass.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## frontdir` + `## backdir → Recorded`, execute tasks, fill `### Recorded`, update this file, append History, `mv HANDOFF.md ../docker/HANDOFF.md` or `../HANDOFF.md`.
- **Append only** — never rewrite this file.

> Full protocol: `../HANDOFF_PROTOCOL.md`
