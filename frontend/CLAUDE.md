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

## Files Panel
- 📎 button in header — amber + count when files attached
- 2 tabs: Library / Attached
- Library per-file: status badge, rename (inline), ✎ rename, 👁 view, ⬇ download, +/✓ attach, 🗑 delete
- Attached per-file: status badge, filename, 👁 view, ✕ detach
- Processing status: SSE stream per file (not polling); `AbortController` stored in `statusStreamsRef`
- Upload button + URL ingest input; workspace filter pills

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
- ⚙ settings modal: system prompt + model lock
- Ctx button — toggles memory_enabled
- Sidebar shows 🔒 when locked model set

## Markdown CSS
Scoped to `.md-body`, injected via `<style>` tag.
Covers: `p`, `h1-h4`, `code` (inline + block `pre`), `ul/ol/li`, `blockquote`, `table/th/td`, `a`, `strong`, `em`, `hr`

---

## Possible Next Features
Suggestions only — ask for specs before implementing.

### UX / Frontend
- **Conversation search** — sidebar filter; backend `GET /conversations?q=`
- **Message editing** — resend edited user message; truncate conv to that point
- **Conversation export** — markdown or JSON; `GET /conversations/{id}/export`
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
