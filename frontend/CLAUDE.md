# Frontend Reference

## Stack
- React + Vite; `vite.config.js` proxies `/api` → `localhost:8000`
- `src/App.jsx` — login form, JWT in localStorage as `nim_token`
- `src/components/Chat.jsx` — orchestrator; imports hooks + sub-components under `chat/`
- `src/hooks/` — 10 hooks: useConversations, useMemory, useWorkspace, useFiles, useModelParams, useSettings, useToolLogs, useUsage, useAdmin, useInsights
- `src/components/chat/` — 12 sub-components: Sidebar, MessageList, ModelToolbar, SettingsModal, WorkspaceModal, FilesPanel, FileViewer, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel
- **All fetch calls must use `/api/` prefix** — bare paths bypass proxy and 404 silently
- **JWT flow:** login → `POST /api/auth/token` → store token as `nim_token` in localStorage → `Authorization: Bearer` on all fetch calls

---

## Chat.jsx — Key Features
- Streaming: raw `<p>` + blinking cursor → done → `<ReactMarkdown>` in `.md-body`
- Per-bubble: `{totalTokens} tok · $x.xxxxx · [query_type] · N src`; live from SSE "done" (`query_type`, `src_count`, `provenance[]` fields); `[query_type]` = factual/relational/temporal/broad; `· N src` badge green ≥3, amber 1–2, hidden if 0
- **Workspace filter pills** — loaded from `GET /api/workspaces` on mount; "All" + per-workspace; ⚙ edit/delete + create; `workspace_id` sent in every `/api/chat/stream` request; selected workspace persisted to `localStorage` key `nim_sidebar_ws_id` via `useWorkspace.js`; validated against loaded list on mount, cleared if ID no longer exists
- **Workspace modal** — create/edit; fields: name, description, system_prompt; delete with confirm
- **Conversation search** — debounced 300ms; `GET /api/conversations?q=`; clears on empty
- **Conversation export** — ⬇ per conv; `GET /api/conversations/{id}/export?format=markdown`
- **Invite panel** (admin) — ⚡ button; load `GET /api/auth/invites`; generate `POST /api/auth/invite`; click to copy
- **Admin endpoints** (API-only, no frontend panel): `/api/admin/users`, `/api/admin/users/{id}/cost-limit`, `/api/admin/audit-log`
- **$ Usage panel** — slide-in; aggregate `GET /api/usage`
- **Compare mode** — same streaming/done split per model card

## Files Panel
- 📎 header button; amber + count when files attached; 2 tabs: Library / Attached
- Library: status badge · inline rename · 👁 view · ⬇ download · +/✓ attach · 🗑 delete
- Processing: SSE per file (not polling); `AbortController` in `statusStreamsRef`
- Workspace filter from `GET /api/files/workspaces` → `{workspaces:[{id,name}]}`; `wsFilter` is UUID

## File Viewer Modal
- 3 tabs: **View** (`<pre>` + download) · **Edit** (textarea → `PUT /api/files/{id}/content`) · **Versions** (list + restore)
- Closes on overlay click or ✕

## Tool Log Panel
- 🔧 button → slide-in; `GET /api/tool-calls?conversation_id=&limit=100`
- Filter: This conversation / All; per-row: tool name (purple), timestamp, args, result preview

## Panels & Cards
- **Last session banner**: muted line `✦ Last session: "…" — X ago` above first AI bubble on SSE `done.last_session`; `lastSession` state in `useConversations.js`; auto-dismisses after 8s or on next send
- **Proactive suggestion**: indigo card below chat feed on `{type:"proactive"}` SSE; ✕ dismiss; clears on next send
- **Insights**: 💡 button; unread badge; `GET /api/insights`; click → mark read; 🗑 delete; indigo dot for unread
- **ask_user**: amber card "NEEDS CLARIFICATION" on `{type:"ask_user"}` SSE; user reply resumes with full context
- **confirm_write_memory**: green card "MEMORY SUGGESTION" on `{type:"confirm_write_memory", fact}` SSE; Accept → `POST /api/memory/write {fact}`, Dismiss → null; clears on next send
- **Memory panel**: tabs View / [Workspace] / Edit / History / Graph — "Workspace" tab appears only when a workspace is selected; View tab renders per-fact cards from `memData.facts[]` (each line = one card, salience % badge green/amber/grey), then PROJECT STATE section, then WORKSPACE section (inline workspace memory from `GET /api/workspaces/{id}/memory` when sidebarWsId set); falls back to splitting `content` by newline if `facts`/sections missing; Workspace tab: full workspace memory view + inline edit + `Updated` timestamp; Graph tab: `GET /api/graph/stats` → `{available, entities, relations}`; auto-refreshes 2s after each AI reply if tab open; `useMemory.js` loads workspace memory whenever memOpen + (memTab=view or workspace)
- **Re-embed button**: ↺ Re-embed All in Invite panel admin section → `POST /api/admin/re-embed`

## Model Control Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B · ⊞ Compare · ⚙ params (temp, max_tokens, top_p with per-slider enable)
- ⚙ settings modal: system prompt · model lock · workspace selector (`PATCH /api/conversations/{id}` with workspace_id)
- Ctx button: toggles memory_enabled · sidebar shows 🔒 when model locked

## Markdown CSS
Scoped to `.md-body` via `<style>` tag. Covers: p · h1-h4 · code/pre · ul/ol/li · blockquote · table · a · strong · em · hr

---

## HANDOFF Protocol — Quick Reference

- **Role:** frontend worker. Do not plan or delegate.
- **Scope:** `frontend/` files only. Cross-dir → `HANDOFF.md` section + pass.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## frontdir` + `## backdir → Recorded`, execute tasks, fill `### Recorded`, update this file, append History, `mv HANDOFF.md ../docker/HANDOFF.md` or `../HANDOFF.md`.
- **Append only** — never rewrite this file.

> Full protocol: `../HANDOFF_PROTOCOL.md`
