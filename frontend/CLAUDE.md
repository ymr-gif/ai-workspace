# Frontend Reference

## Stack
- React + Vite; `vite.config.js` proxies `/api` → `localhost:8000`
- `src/App.jsx` — login form, JWT in localStorage as `nim_token`
- `src/components/Chat/index.jsx` — orchestrator; uses `useStreamChat` hook for SSE, `closeAllExcept` helper, wraps panels in `<PanelPropsCtx.Provider>` with all hook state as single object
- `src/components/Chat/PanelPropsContext.js` — React context eliminating prop drilling; panels consume via `usePanelProps()`
- `src/lib/chatStyles.js` — shared style objects; `LAYERS` constant for z-indices, `panelBase` for all slide-in panels
- `src/hooks/` — 17 hooks: useConversations, useMemory, useFiles, useModelParams, useSettings, useToolLogs, useUsage, useAdmin, useInsights, useSearch, useScheduledPrompts, useGoals, useIntegrations, useNotificationPrefs, useOnboarding, useStreamChat, useVoice
- `src/components/Chat/*/index.jsx` — 16 sub-components: Sidebar, MessageList, ModelToolbar, SettingsModal, FilesPanel, FileViewer, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel, SearchPanel, AutomationsPanel, GoalsPanel, IntegrationsPanel, OnboardingModal
- **All fetch calls must use `/api/` prefix** — bare paths bypass proxy and 404 silently
- **JWT flow:** login → `POST /api/auth/token` → store token as `nim_token` in localStorage → `Authorization: Bearer` on all fetch calls
- **Open-conversation persistence:** `useConversations.js` stores `activeConvId` in localStorage as `nim_active_conv` (init from it, write on change, removed when null) → a full tab refresh reopens the same conversation (badge + history restored) instead of an empty chat. Browser-local only; a missing/deleted id fetches `[]` harmlessly

---

## Chat/index.jsx — Key Features
- **SSE streaming extracted to `useStreamChat` hook** — `Chat/index.jsx` calls `const { send, buildBody } = useStreamChat({ token, conv, modelParams, mem, insights, onLogout, onCalendarWrite })`. The hook manages all streaming state internally.
- Streaming: raw `<p>` + blinking cursor → done → `<ReactMarkdown>` in `.md-body`
- Per-bubble: `{totalTokens} tok · $x.xxxxx · [query_type] · N src · web · url`; live from SSE "done" (`query_type`, `src_count`, `provenance[]`, `web_searched`, `url_fetched` fields); `[query_type]` = factual/relational/temporal/broad; `· N src` badge green ≥3, amber 1–2, hidden if 0; `web` cyan badge (`background:#0e7490`) when `web_searched === true`; `url` blue badge (`background:#0369a1`) when `url_fetched === true`
- **Grounding badge + reasoning trace** (ROADMAP Dim 3): from SSE `done` fields `grounding {level,score,sources}` + `activity[]` + `intent` (stored on the message in `useStreamChat.js`). `MessageList/index.jsx` renders a per-bubble badge when `grounding.level !== 'none'`: a small 7px CSS dot (no emoji — `borderRadius:50%`, `background:c`) + `High · 82%` / `Medium · 55%` / `Low · 28%` (dot + text color GRN/AMB/RED by level). Clicking the badge toggles `m.traceExpanded` (via `setMessages`, same pattern as tool pills) → inline "Reasoning steps" timeline rendered from `m.activity[]` (one row per stage `detail` + optional `ms`, color by `level`: error=RED/warn=AMB/info=FG4). Includes the `Intent: <x>` row. Pipeline-level trace, **not** model chain-of-thought. **Persisted:** `useConversations.js` maps `grounding`/`query_type`/`src_count` (from `render_meta`) + `activity_trace` on the message refetch, so the badge + trace survive the post-send new-conversation refetch, full reload, and history load — not live-only.
- **Conversation search** — debounced 300ms; `GET /api/conversations?q=`; clears on empty
- **Conversation export** — ⬇ per conv; `GET /api/conversations/{id}/export?format=markdown`
- **Invite panel** (admin) — ⚡ button; load `GET /api/auth/invites`; generate `POST /api/auth/invite`; click to copy
- **Admin endpoints** (API-only, no frontend panel): `/api/admin/users`, `/api/admin/users/{id}/cost-limit`, `/api/admin/audit-log`
- **$ Usage panel** — slide-in; aggregate `GET /api/usage`; **⬇ Export All Data** button at bottom → `GET /api/export/full` (bearer token header) → downloads `export.zip` (conversations · files · memory · graph); token passed as prop from `Chat.jsx`
- **Compare mode** — same streaming/done split per model card
- **Automations panel** (ROADMAP #12) — ⏱ Auto header button; slide-in; `useScheduledPrompts.js`; CRUD for scheduled prompts via `/api/scheduled-prompts`; create/edit form with preset aliases (daily/weekly/monthly) or custom cron, optional model_override; per-row: active toggle (`PATCH is_active`) · ▶ Run (`POST /run`) · ▼ Runs (expandable run history from `GET /id/runs`) · Edit · 🗑 delete; form overlays panel with zIndex:2
- **Goals panel** (ROADMAP #13) — 🎯 Goals header button; slide-in; `useGoals.js`; CRUD via `/api/goals`; status filter pills (all/active/paused/completed); per-card: StatusBadge · linked conv count · toggle active↔paused · 🔗 Link conv (if `activeConvId` set + goal active, `POST /goals/{id}/link/{convId}`, disabled if already linked) · Edit · 🗑 delete; create/edit form overlay (title, description, status dropdown)
- **Integrations panel** — Integrations header button; slide-in; `useIntegrations.js`; sources list from `GET /api/integrations`; per-card status badge, sync button (`POST /api/integrations/{id}/sync`), delete (`DELETE`); **All connectors currently render as "More integrations on the way"** with a "Soon" badge (opacity 0.6, no OAuth button) — `ENABLED_CONNECTOR_TYPES = []` in `useIntegrations.js`. To expose a connector with live OAuth: add its type to `ENABLED_CONNECTOR_TYPES`. The `startOAuth()` function, popup-closed polling, popup-blocked banner, and error banner are all still present and functional — just not reachable while no types are enabled.
- **⬡ Canvas button** — opens `/canvas/index.html` in a new tab; styled red (`color:RED, borderColor:RED`); placed in header before Logout; canvas checks `nim_token` in localStorage and redirects to `/` if missing

## Files Panel
- 📎 header button; amber + count when files attached; 2 tabs: Library / Attached
- Library: status badge · inline rename · 👁 view · ⬇ download · +/✓ attach · 🗑 delete
- Processing: SSE per file (not polling); `AbortController` in `statusStreamsRef`
- Image files (`media_type === "image"`): 36×36 thumbnail via `/api/files/{id}/download`; `ocr_text` snippet below filename

## File Viewer Modal
- 3 tabs: **View** (`<pre>` + download) · **Edit** (textarea → `PUT /api/files/{id}/content`) · **Versions** (list + restore)
- Image files (`mime_type` starts with `image/`): 4 tabs — **Preview** (renders `<img>` via download URL) · **Raw** · **Edit** · **Versions**; defaults to Preview tab
- Closes on overlay click or ✕

## Voice Input (Phase 1b)
- `useVoice.js` hook manages `MediaRecorder` + `POST /api/transcribe`
- Mic button (`MIC`/`REC`/`BUSY`) left of input bar in `ModelToolbar/index.jsx`
- Probes endpoint on mount (503 = disabled, hides button)
- Transcript injected into input via `conv.setInput(text)`
- Stub placeholder text shown as-is (no special-casing)
- Styles: `micBtn` (muted) / `micRec` (red border + glow) in `chatStyles.js`

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
- **confirm_calendar_write**: sky card "CALENDAR SUGGESTION" on `{type:"confirm_calendar_write", op, args, summary}` SSE; Accept → `POST /api/integrations/calendar/execute {op, args}`, Dismiss → null; state in `Chat/index.jsx` local `pendingCalendarWrite` + `onCalendarWrite` callback passed to `useStreamChat`; toast on success/failure; clears on next send
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
- Response shape: `{ query, scope, results: [{ source, score, title, snippet, id, media_type? }] }` — `media_type` present for file results only (`"image"`/`"document"`)
- File results with `media_type === "image"` show a cyan `img` badge next to the score

## Onboarding / First-Run Wizard (Phase 3b)
- `useOnboarding.js` hook reads `has_onboarded` from `GET /api/auth/me` on mount; opens modal if `false`
- `OnboardingModal/index.jsx` — 3-step skippable wizard: Welcome → Email (`PATCH /api/auth/me/email`) → Integrations (reuses `integ.startOAuth()`) → Finish/Skip (`POST /api/auth/me/onboarding-complete`)
- Z-index: `LAYERS.onboarding` (50) — above all panels and modals
- Step dots rendered as circles in footer; "Skip onboarding" always visible

## Notifications (Phase 3c)
- `useNotificationPrefs.js` — loads prefs from `GET /api/notifications/preferences` + VAPID key from `GET /api/notifications/vapid-public-key` on mount; registers `/sw.js` service worker
- Toggles (instant-save `PATCH /api/notifications/preferences`): email_digest, email_scheduled, email_insights, push_enabled
- Push toggle: ON → `Notification.requestPermission()` → `PushManager.subscribe()` → `POST /api/notifications/push/subscribe`; OFF → `unsubscribe()`
- Toggles rendered in SettingsModal notification section
- `public/sw.js` — handles `push` and `notificationclick` events; shows browser notification with title/body from payload

## Model Control Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B · ⊞ Compare · ⚙ params (temp, max_tokens, top_p with per-slider enable)
- ⚙ settings modal: system prompt · model lock (`PATCH /api/conversations/{id}`)
- Ctx button: **OBSOLETE — memory is always-on; this toggle should be removed** · sidebar shows 🔒 when model locked

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
- **`panelBase`** in `chatStyles.js` provides shared slide-in panel styles. All 7 side panels use `{...panelBase, width, maxWidth}` with overrides only for dimension/color differences.

---

## HANDOFF Protocol — Quick Reference

- **Role:** frontend worker. Do not plan or delegate.
- **Scope:** `frontend/` files only. Cross-dir → `HANDOFF.md` section + pass.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## frontdir` + `## backdir → Recorded`, execute tasks, fill `### Recorded`, update this file, append History, `mv HANDOFF.md ../docker/HANDOFF.md` or `../HANDOFF.md`.
- **Append only** — never rewrite this file.

> Full protocol: `../HANDOFF_PROTOCOL.md`
