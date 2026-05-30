# HANDOFF
- Updated: 2026-05-30
- Status: idle
- Owner: root
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: —

_(no active feature)

---

## Last Completed: User-Defined Scheduled Agents (ROADMAP #12)

### What
Expose the existing `ScheduledPrompt` model as a full user-facing CRUD API, then build an Automations panel in the frontend for creating, editing, deleting, and viewing scheduled prompt runs.

### Context
`ScheduledPrompt` and `ScheduledPromptRun` models already exist in `backend/models/prompts_scheduled.py`. Some CRUD may be partially implemented — check before writing new code.

### Backend tasks
- [x] **Audit existing routes** — `scheduled_prompts.py` already exists with full CRUD (GET list, GET by-id-with-runs, POST create, PATCH update, DELETE, GET runs, POST trigger-run). Already registered in `main.py`.
- [x] **Expose full CRUD** — extended existing `scheduled_prompts.py`:
  - Added `schedule` field (accepts `daily`/`weekly`/`monthly` aliases + cron strings) to Create/Patch schemas
  - Added optional `workspace_id` (UUID, FK to workspaces) to schemas + model + migration 034
  - Added `workspace_id` to `_schedule_row()` response
- [x] **Register router** — already registered in `main.py` (line 123)
- [x] **Record** findings + schema details in `### Recorded` before passing.

### Files to touch
- `backend/api/scheduled_prompts.py` — new or extend
- `backend/main.py` — include router if missing

### Frontend tasks
- [x] **`useScheduledPrompts.js` hook** — `prompts` state; `loadPrompts` (`GET /api/scheduled-prompts`); `createPrompt`, `updatePrompt`, `deletePrompt`, `triggerRun` (`POST /api/scheduled-prompts/{id}/run`); bearer token from `localStorage.getItem("nim_token")`.
- [x] **`AutomationsPanel.jsx` slide-in** — ⏱ Auto button in `Chat.jsx` header opens panel; lists all scheduled prompts as cards (name, schedule badge, workspace name if set, active toggle → `PATCH is_active`).
- [x] **Create / edit form** — inline overlay; fields: name (text), prompt (textarea), schedule picker (pills: Daily / Weekly / Monthly / Custom; custom shows cron input), workspace selector (dropdown from existing workspaces list), model override (optional); submit → `POST` or `PATCH`.
- [x] **Delete** — 🗑 per card; `DELETE /api/scheduled-prompts/{id}`.
- [x] **Run history** — expandable section per card; `GET /api/scheduled-prompts/{id}/runs` → list of runs with `started_at`, `status`, error; ▶ Run button → `POST /api/scheduled-prompts/{id}/run`.

### Files to touch
- `frontend/src/hooks/useScheduledPrompts.js` — new
- `frontend/src/components/chat/AutomationsPanel.jsx` — new
- `frontend/src/components/Chat.jsx` — button + panel mount

### Pass instructions
When done: `mv` to `../HANDOFF.md`.

### Recorded

**Audit result:** All CRUD routes already exist in `backend/api/scheduled_prompts.py` (233 lines). Router registered in `main.py` at `/scheduled-prompts`. No new router needed.

**Changes made:**
- `models/prompts_scheduled.py`: added `workspace_id` column (UUID, FK workspaces.id, ondelete=SET NULL, nullable, indexed)
- `alembic/versions/034_scheduled_prompt_workspace.py`: migration adding the column + index
- `api/scheduled_prompts.py`: 
  - Added `_SCHEDULE_ALIASES` mapping: `daily`→`0 0 * * *`, `weekly`→`0 0 * * 0`, `monthly`→`0 0 1 * *`
  - Added `_resolve_schedule()` helper — resolves aliases, passes through cron strings
  - `ScheduleCreate.schedule` — accepts aliases or cron; validated via `croniter`
  - `SchedulePatch.schedule` — same, nullable for partial update
  - `workspace_id` (str, optional) in both Create and Patch schemas
  - `_schedule_row()` includes `workspace_id`

**Endpoints (all existing):**
| Method | Path | Description |
|--------|------|-------------|
| GET | /scheduled-prompts | List user's schedules |
| POST | /scheduled-prompts | Create (body: name, prompt, schedule, model_override?, workspace_id?) |
| GET | /scheduled-prompts/{id} | Get with recent_runs[] |
| PATCH | /scheduled-prompts/{id} | Update (name, prompt, schedule, model_override, workspace_id, is_active) |
| DELETE | /scheduled-prompts/{id} | Delete (204) |
| GET | /scheduled-prompts/{id}/runs | List run history (last 20) |
| POST | /scheduled-prompts/{id}/run | Trigger manual run (202) |

**Files touched:** `backend/models/prompts_scheduled.py`, `backend/alembic/versions/034_scheduled_prompt_workspace.py`, `backend/api/scheduled_prompts.py`

---

## History
| Date       | Feature                          | Notes |
|------------|----------------------------------|-------|
| 2026-05-30 | Knowledge Graph Explorer UI      | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Unified Search (ROADMAP #7)      | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Fact-Level Salience Panel        | root → frontdir (done) |
| 2026-05-30 | Memory Conflict Resolution UI    | root → frontdir (done) |
| 2026-05-30 | Security & perf fixes            | frontdir (done) — role bug, stale closure, URL encode, useMemo |
| 2026-05-30 | Cross-Session Continuity Summary | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Behavioral Pattern Tracker       | root → backdir → done |
| 2026-05-30 | User Preference Extraction       | root → backdir → done |
| 2026-05-29 | Chat.jsx Refactor                | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing        | plan → backdir (done) → frontdir (done) |
| 2026-05-30 | Full Data Export (ROADMAP #10)   | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Scheduled Backup (ROADMAP #11)   | root → backdir (done) |
| 2026-05-30 | User-Defined Scheduled Agents (ROADMAP #12) | root → backdir (done) → frontdir |
