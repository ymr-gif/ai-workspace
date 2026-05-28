# Frontend Reference

## Stack
- React + Vite; `vite.config.js` proxies `/api` → `localhost:8000`
- `src/App.jsx` — login form, JWT in localStorage as `nim_token`
- `src/components/Chat.jsx` — full UI
- **All fetch calls must use `/api/` prefix** — bare paths bypass proxy and 404 silently

---

## Chat.jsx — Key Features
- Streaming: raw `<p>` + blinking cursor → done → `<ReactMarkdown>` in `.md-body`
- Per-bubble: `{totalTokens} tok · $x.xxxxx`; live from SSE "done", history from messages endpoint
- **Workspace filter pills** — loaded from `GET /api/workspaces` on mount; "All" + per-workspace; ⚙ edit/delete + create; `workspace_id` sent in every `/api/chat/stream` request
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
- **Proactive suggestion**: indigo card below chat feed on `{type:"proactive"}` SSE; ✕ dismiss; clears on next send
- **Insights**: 💡 button; unread badge; `GET /api/insights`; click → mark read; 🗑 delete; indigo dot for unread
- **ask_user**: amber card "NEEDS CLARIFICATION" on `{type:"ask_user"}` SSE; user reply resumes with full context
- **Memory panel**: tabs View / Edit / History / Graph (5th tab); Graph tab: `GET /api/graph/stats` → `{available, entities, relations}`; auto-refreshes 2s after each AI reply if tab open
- **Re-embed button**: ↺ Re-embed All in Invite panel admin section → `POST /api/admin/re-embed`

## Model Control Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B · ⊞ Compare · ⚙ params (temp, max_tokens, top_p with per-slider enable)
- ⚙ settings modal: system prompt · model lock · workspace selector (`PATCH /api/conversations/{id}` with workspace_id)
- Ctx button: toggles memory_enabled · sidebar shows 🔒 when model locked

## Markdown CSS
Scoped to `.md-body` via `<style>` tag. Covers: p · h1-h4 · code/pre · ul/ol/li · blockquote · table · a · strong · em · hr

---

## HANDOFF Protocol

### Role
Worker for `frontend/` only. Root plans; this agent implements.

**Scope rule:** If a task belongs outside `frontend/` — do not implement it. Instead:
1. Note it in `HANDOFF.md` under the correct dir section (`## backdir` or `## dockdir`)
2. Pass the file to that dir when done with frontend tasks

**Root escalation:** Do not edit root-level files directly. Pass back to root (`../HANDOFF.md`, status: needs-root) for any changes to:
`.env` · `.env.example` · `.gitignore` · `.dockerignore` · `CLAUDE.md` (root) · `README.md` · `ROADMAP.md`
or any file not clearly owned by `backend/`, `frontend/`, or `docker/`.

**CRITICAL — never delete or overwrite root files.** `CLAUDE.md` at repo root is root-owned. Do not touch it under any circumstances.

**CRITICAL — never rewrite this file.** When updating `frontend/CLAUDE.md`, append to existing sections only. Do not truncate, replace, or delete content.

---

On session start — check if `frontend/HANDOFF.md` exists:
```bash
ls HANDOFF.md 2>/dev/null && echo "YOUR TURN" || echo "no handoff"
```

If it exists:
1. Read `## frontdir` Tasks section
2. Read `## backdir → Recorded` — use exact endpoint shapes, SSE event names, env vars listed there
3. Execute all tasks (check off as done); add addenda if Recorded reveals extra work
4. Fill `### Recorded` with facts for dockdir if applicable
5. **Update `frontend/CLAUDE.md`** — add any new panels, tabs, buttons, or fetch endpoints introduced by the feature
6. Append a History row
7. Move file:
   ```bash
   mv HANDOFF.md ../docker/HANDOFF.md   # if dockdir has tasks
   mv HANDOFF.md ../HANDOFF.md          # if done — set status: done
   ```

All fetch calls use `/api/` prefix.
