# Frontend Reference

## Stack
- React + Vite; `vite.config.js` proxies `/api` → `localhost:8000`
- `react-markdown` + `remark-gfm` installed
- `src/App.jsx` — login form, JWT in localStorage as `nim_token`
- `src/components/Chat.jsx` — full UI

## Chat.jsx — Key Features
- AI responses: streaming → raw `<p>` + blinking cursor; done → `<ReactMarkdown>` in `.md-body`
- User messages and errors stay plain text
- Compare mode: same streaming/done split per model card
- Per-bubble token display: `{totalTokens} tok · $x.xxxxx` below model tag when done
  - Live: from SSE "done" event; history: from messages endpoint
- `$ Usage` button → slide-in panel (aggregate `/api/usage`): messages, tokens, cost + refresh
- **Workspace filter pills** in sidebar — loaded from `GET /workspaces` on mount
  - "All" pill + one pill per workspace; active pill filters conversation list
  - Each workspace pill has ⚙ (edit/delete) and + (create) buttons → workspace modal
  - `workspace_id` sent in every `/chat/stream` request (null = backend picks Default)
  - New conversations in SSE "done" event include `workspace_id` for immediate sidebar filter
- **Workspace modal** — create or edit workspace
  - Fields: name, description, system prompt
  - Delete button (with confirm) on edit mode
  - `POST /workspaces` / `PATCH /workspaces/{id}` / `DELETE /workspaces/{id}`
- **Conversation search** — debounced input above conversation list (300ms)
  - Calls `GET /conversations?q=` on input; shows results inline; clears on empty
- **Conversation export** — ⬇ button per conversation in sidebar
  - Downloads via `GET /conversations/{id}/export?format=markdown` (Content-Disposition attachment)
- **Invite panel** (admin only) — ⚡ button in header
  - Loads from `GET /auth/invites`; generate token via `POST /auth/invite`
  - Click token text to copy to clipboard
  - Shows: token, expires, status (unused / used by <username>)

## Files Panel
- 📎 button in header — amber + count when files attached
- 2 tabs: Library / Attached
- Library per-file: status badge, rename (inline), ✎ rename, 👁 view, ⬇ download, +/✓ attach, 🗑 delete
- Attached per-file: status badge, filename, 👁 view, ✕ detach
- Processing status: SSE stream per file (not polling); `AbortController` stored in `statusStreamsRef`
- Upload button + URL ingest input
- Workspace filter pills from `GET /files/workspaces` → `{workspaces: [{id, name}]}`
  - `wsFilter` is a UUID string (was plain string in old API)

## File Viewer Modal
- 3 tabs:
  - **View**: `<pre>` of content + ⬇ Download
  - **Edit**: textarea (pre-filled) + Save/Cancel → PUT /files/{id}/content
  - **Versions**: list (version #, date, size) + Restore per version
- Closes on overlay click or ✕

## Tool Log Panel
- 🔧 Log button → slide-in; state: `toolLogOpen`, `toolLogs`, `toolLogsLoading`
- Loads from `GET /tool-calls?conversation_id=&limit=100`
- Filter pills: This conversation / All
- Per-row: tool name (purple), timestamp, args summary, result preview

## ask_user Flow
1. Model calls `ask_user(question="...")`
2. Backend yields `{type:"ask_user", question}` SSE + done
3. Frontend: sets `m.askUser = question`
4. Renders amber card: "NEEDS CLARIFICATION" + question
5. User replies normally → next message resumes with full context

## Model Control Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B
- ⊞ Compare toggle
- ⚙ params expander: temp, max_tokens, top_p (per-slider enable checkboxes)
- ⚙ settings modal: system prompt, model lock, **workspace selector** (dropdown of user's workspaces)
  - Workspace change: `PATCH /conversations/{id}` with `workspace_id`
- Ctx button — toggles memory_enabled
- Sidebar shows 🔒 when locked model set

## Memory Panel
- Tabs: User / Workspace (visible when workspace is selected in sidebar) / History
- Workspace tab: loads `GET /workspaces/{id}/memory`; view + inline edit; `PUT /workspaces/{id}/memory` to save
  - Tracks version number; shows last updated timestamp

## Markdown CSS
Scoped to `.md-body`, injected via `<style>` tag.
Covers: `p`, `h1-h4`, `code` (inline + block `pre`), `ul/ol/li`, `blockquote`, `table/th/td`, `a`, `strong`, `em`, `hr`

---

## Possible Next Features
Suggestions only — ask for specs before implementing.

### UX / Frontend
- **Message editing** — resend edited user message; truncate conv to that point
- **Drag-and-drop upload** — drop anywhere on chat area
- **Keyboard shortcuts** — `Ctrl+Enter` send, `Ctrl+K` search, `Esc` close panels
- **Mobile layout** — sidebar hamburger, stacked input bar
- **Cost budget alerts** — user-configurable; toast + optional hard block
- **Admin frontend panel** — user table + usage + enable/disable; currently API-only

### RAG / Memory
- **Re-embed on model change** — MODEL_EMBEDDING change makes old chunks stale
- **Per-conversation memory** — separate sheet per conv, not just per user
- **Graph memory** — entities + relationships; richer than flat key-value

### Token / Cost
- **Budget dashboard** — Grafana panels per user (PostgreSQL group-by user_id)
- **Monthly rollup** — aggregate table beyond Prometheus window
- **Cost cap rolling window** — currently all-time; monthly reset more practical

### Observability / Admin
- **User activity timeline** — last N messages per user with timestamps + models
- **Memory system metrics** — Prometheus counters for memory updates, RAG hits
- **Grafana alerts** — error rate >5%, latency p95 >10s, cost spike
- **Usage CSV export** — `GET /admin/export/usage.csv`

### Infrastructure
- **Prometheus remote write** — persist metrics across restarts
- **Automated backup verification** — weekly restore test to temp DB

### Security (lowest priority — home/LAN deployed)
- **Prompt injection detection** — heuristic before passing to model
- **API key auth** — alternative to JWT; `User.api_key` column
- **CORS lockdown** — restrict to known frontend origin in production
- **OpenAI-compatible endpoint** — `POST /v1/chat/completions` wrapper
