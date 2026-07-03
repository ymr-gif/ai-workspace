# Manual Verification Runbook — JARVIS / NIM AI Gateway

Copy-paste runbook for verifying live behavior without burning agent tokens.
Every command is self-contained. Run from the repo root: `~/dev/python-projects/ai-api`.

Covers:
- **Suite A** — Drive tools (bugs M1–M6, N1)
- **Suite B** — Memory Hygiene + Safe Reset (S1–S4, §O)
- **Suite C** — unit tests
- **Appendix** — event/field reference + gotchas

---

## 0. Prerequisites & conventions

### Services must be up
```bash
docker compose -f docker/docker-compose.yml ps api arq-worker postgres redis neo4j
curl -s http://localhost:8000/health | python3 -m json.tool   # expect status:ok, nim:ok
```

### Credentials (all local/dev)
| Thing | Value |
|-------|-------|
| API base URL | `http://localhost:8000` |
| Seeded admin | `admin` / `admin-secret` (role: admin) |
| Seeded user | `user` / `user-secret` |
| Postgres | user `scylla`, db `nimrouter` (via `docker compose exec postgres`) |
| Redis | no auth (via `docker compose exec redis redis-cli`) |
| Neo4j | `neo4j` / `changeme` (via `docker compose exec neo4j cypher-shell`) |
| Drive connected to | `admin` (user_id = 1) |

### Conventions
- Auth = **JWT Bearer** in `Authorization: Bearer $TOK`.
- The token **expires** — if any call returns `401`, re-run Step 1 to refresh `$TOK`.
- `/chat/stream` is **SSE**: each line is `data: {json}`. Parse with the helper in Step 2.
- **Cache bypass:** the response cache is keyed on msg+model+history+sysprompt and is
  bypassed when the body contains `temperature`, `max_tokens`, `image_b64`, or attached files.
  Always pass `"temperature"` (and a small `"max_tokens"`) so you exercise live code, not a
  stale cached answer. A `done` event with `"cache_hit": true` means you hit the cache — change
  wording or add/raise `temperature`.
- **Capturing `conversation_id`:** the `done` event carries it, but a long generation can hit
  curl's `-m` timeout before `done`. Cap `"max_tokens": 250` so `done` always arrives.

---

## 1. Get an auth token  (do this first, reuse `$TOK` everywhere)

```bash
export TOK=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin-secret" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "${TOK:0:16}...   (empty = login failed)"
```
> `/auth/token` is OAuth2 password form — **form-encoded, not JSON**. Field names `username`/`password`.

---

## 2. Reusable SSE parser  (save once, pipe any /chat/stream output into it)

```bash
cat > /tmp/sse.py <<'PY'
import sys, json
tools=[]; content=[]; done=None; rotated=None
for ln in sys.stdin:
    if not ln.startswith('data:'): continue
    try: ev=json.loads(ln[5:].strip())
    except: continue
    t=ev.get('type')
    if t in ('tool_call','tool_result'): tools.append((t, ev.get('name'), str(ev.get('content',''))[:70]))
    if t in ('content','token'): content.append(ev.get('content',''))
    if t=='rotated': rotated=ev
    if t=='done': done=ev
print('TOOLS:', tools or 'NONE')
if rotated: print('ROTATED:', rotated)
if done: print('DONE:', {k:done.get(k) for k in ('model','cache_hit','drive_read','web_searched','conversation_id')})
print('--- reply (first 600) ---'); print(''.join(content)[:600])
PY
```

Generic chat call (fill MESSAGE; add `,"conversation_id":"..."` for a follow-up turn):
```bash
curl -s -N -m 180 -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"message":"MESSAGE","temperature":0.3,"max_tokens":300}' | python3 /tmp/sse.py
```

---

## 3. State inspectors  (DB / Redis / graph)

```bash
PG(){ docker compose -f docker/docker-compose.yml exec -T postgres psql -U scylla -d nimrouter "$@"; }
RED(){ docker compose -f docker/docker-compose.yml exec -T redis redis-cli "$@"; }
CY(){ docker compose -f docker/docker-compose.yml exec -T neo4j cypher-shell -u neo4j -p changeme --format plain "$@"; }
```
```bash
# memory sheet for admin
PG -tAc "SELECT length(content)||' chars' FROM user_memory WHERE user_id=1;"
PG -c  "SELECT left(content,400) FROM user_memory WHERE user_id=1;"
# what got embedded for a conversation (reference vs body)
PG -c  "SELECT left(content_snippet,160) FROM message_embeddings WHERE conversation_id='CONV_ID' ORDER BY created_at DESC LIMIT 3;"
# Drive listing cache (set after a list; 3600s TTL)
RED KEYS "drive_listing:*"
RED TTL  "drive_listing:CONV_ID"
RED HKEYS "drive_listing:CONV_ID"
# graph entity count + dup check
CY "MATCH (e:Entity {user_id:1}) RETURN count(e);"
CY "MATCH (e:Entity) WHERE e.name =~ '(?i).*(xeon|p40).*' RETURN e.name, e.type;"
```

---

## 4. Suite A — Drive tools (M1–M6, N1)

Run turns **in order, same `$TOK`**. Capture the conversation id from turn A1's `DONE`.

| # | Message | Body extras | Expect |
|---|---------|-------------|--------|
| A1 | `list my drive files please` | `temperature:0.4, max_tokens:250` | `TOOLS` has `drive_list_files`; `DONE.cache_hit=false`; grab `conversation_id` |
| A2 | `the issue is backend, stale memory with 6 symptoms` | + `conversation_id`, `temperature:0.3` | **TOOLS: NONE**, no file listing in reply (N1) |
| A3 | `read JARVIS Test Note` | + `conversation_id`, `temperature:0.3` | `TOOLS` has `drive_read_file` (not list); `DONE.drive_read=true` (M6/L1/L2) |
| B1 | `M1 Live Drive reads poison persistent memory` | **new conv** (no conversation_id), `temperature:0.4` | **TOOLS: NONE**, no listing (M2 keyword tighten) |

A1 (capture conv id):
```bash
CONV=$(curl -s -N -m 150 -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"message":"list my drive files please","temperature":0.4,"max_tokens":250}' \
  | tee /tmp/a1 | grep -o '"conversation_id": *"[^"]*"' | head -1 | grep -o '[0-9a-f-]\{36\}')
echo "CONV=$CONV"; python3 /tmp/sse.py < /tmp/a1
```
A2 / A3 (reuse `$CONV`):
```bash
curl -s -N -m 150 -X POST http://localhost:8000/chat/stream -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"the issue is backend, stale memory with 6 symptoms\",\"conversation_id\":\"$CONV\",\"temperature\":0.3,\"max_tokens\":250}" | python3 /tmp/sse.py

curl -s -N -m 180 -X POST http://localhost:8000/chat/stream -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"read JARVIS Test Note\",\"conversation_id\":\"$CONV\",\"temperature\":0.3,\"max_tokens\":300}" | python3 /tmp/sse.py
```
Fix-1 check (memory holds a **reference, not the file body**) after A3:
```bash
PG -c "SELECT left(content_snippet,160) FROM message_embeddings WHERE conversation_id='$CONV' ORDER BY created_at DESC LIMIT 2;"
# PASS = assistant snippet reads "User viewed Drive file '...' — content fetched live, not cached."
```

---

## 5. Suite B — Memory Hygiene + Safe Reset (S1–S4, §O)

### Endpoint
`POST /admin/memory/reset` — admin JWT, JSON body:
```json
{ "user_id": 1, "level": "soft|hard", "dry_run": true, "confirm": "RESET 1" }
```
- `dry_run:true` (default) → returns a **report only**, mutates nothing.
- To mutate: `dry_run:false` **and** `confirm` exactly `"RESET <user_id>"`.
- `soft` = prune dead-Canvas `[CORRECTIONS]` + dedup graph + archive over-threshold convs.
- `hard` = reset sheet to `[USER]` basics, clear graph, archive all convs, start one clean conv.
- Backup (UserMemoryVersion snapshot + export ZIP + graph JSON dump → `backend/storage/backups/`) runs first.

### B1 — Baseline (before)
```bash
PG -tAc "SELECT length(content)||' chars; has_canvas='||(content ILIKE '%canvas%')::text FROM user_memory WHERE user_id=1;"
CY "MATCH (e:Entity {user_id:1}) RETURN count(e);"
PG -tAc "SELECT count(*) FILTER (WHERE is_archived) AS archived, count(*) AS total FROM conversations WHERE user_id=1;"
```

### B2 — DRY RUN (no mutation)
```bash
curl -s -X POST http://localhost:8000/admin/memory/reset \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"user_id":1,"level":"soft","dry_run":true,"confirm":"RESET 1"}' | python3 -m json.tool
# expect a report (corrections pruned, entities merged, convs archived); DB unchanged vs B1
```

### B3 — REAL soft reset (mutates; backup written first)
```bash
curl -s -X POST http://localhost:8000/admin/memory/reset \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"user_id":1,"level":"soft","dry_run":false,"confirm":"RESET 1"}' | python3 -m json.tool
ls -lt backend/storage/backups/ | head    # backup ZIP + graph dump present
```

### B4 — Verify (after)
```bash
PG -tAc "SELECT length(content)||' chars; has_canvas='||(content ILIKE '%canvas%')::text FROM user_memory WHERE user_id=1;"  # smaller; has_canvas=false
CY "MATCH (e:Entity) WHERE e.name =~ '(?i).*(xeon|p40).*' RETURN e.name;"   # collapsed to one each
PG -tAc "SELECT count(*) FILTER (WHERE is_archived) FROM conversations WHERE user_id=1;"  # mega-thread archived
PG -tAc "SELECT version FROM user_memory_versions WHERE user_id=1 ORDER BY version DESC LIMIT 1;"  # new snapshot exists
```

### B5 — Behavior (the real proof)
Open a **new** chat and present the 6 symptoms again (or via WhatsApp JARVIS):
```bash
curl -s -N -m 150 -X POST http://localhost:8000/chat/stream -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{"message":"hello, are you there?","temperature":0.4,"max_tokens":200}' | python3 /tmp/sse.py
```
PASS = no off-by-one symptom recital, no canvas mentions, no pre-emption.

### B6 — S4 rotation (optional, slow)
Drive one conversation past **80 msgs / 120k tokens / 3 days idle**; next turn emits a
`{"type":"rotated", "new_conversation_id", "old_conversation_id"}` SSE event and the old conv gets
`is_archived=true`. Quick check of any already-archived convs:
```bash
PG -c "SELECT left(id::text,8), is_archived, archived_at FROM conversations WHERE user_id=1 AND is_archived ORDER BY archived_at DESC;"
```

### Restore — live endpoint (verified 2026-07-03)
`POST /admin/memory/restore` is implemented and verified (rich-full run: reset → restore → 200,
content swapped, audit row written). Snapshots current sheet before overwriting — reversible.
```bash
curl -s http://localhost:8000/admin/memory/versions?user_id=1 -H "Authorization: Bearer $TOK"
curl -s -X POST http://localhost:8000/admin/memory/restore \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"user_id":1,"version_id":<id>,"confirm":"RESTORE 1"}'   # confirm = "RESTORE <user_id>"
```

---

## 6. Suite C — unit tests (no live services, fast)
```bash
docker compose -f docker/docker-compose.yml exec -T api python -m pytest \
  tests/test_drive.py tests/test_memory_hygiene.py tests/test_content_filter.py -q
# pytest not in the prod image? run on host:
cd backend && python -m pytest tests/test_drive.py tests/test_memory_hygiene.py tests/test_content_filter.py -q
```
Expected (recounted 2026-07-04): `test_drive.py` (8) · `test_memory_hygiene.py` (36) · `test_content_filter.py` (10) — all green.

---

## Appendix

### `/chat/stream` SSE event types
| type | key fields | meaning |
|------|-----------|---------|
| `status` | `stage, detail, level, ms?` | pipeline step (route/cache/budget/tool/fallback) |
| `token` / `content` | `content` | streamed answer text |
| `tool_call` | `name` | model invoked a tool |
| `tool_result` | `name, content` (≤500 char preview) | tool output |
| `rotated` | `new_conversation_id, old_conversation_id` | conversation auto-archived mid-request (S4) |
| `ask_user` | — | tool paused for user input (amber card) |
| `confirm_write_memory` | `fact` | memory-write confirmation (green card) |
| `done` | `model, cache_hit, fallback_used, drive_read, web_searched, url_fetched, conversation_id, provenance` | end of turn |

### Gotchas
- **`cache_hit:true`** → you hit the response cache (a pre-fix answer can be served). Add/raise
  `temperature` or reword. To purge stale cached answers after a deploy: `RED FLUSHDB` (dev only).
- **`401`** mid-run → token expired; re-run Step 1.
- **Empty `conversation_id`** in `DONE` → generation exceeded `-m` timeout before `done`; lower
  `max_tokens` to ~250.
- **Drive token expired** → first Drive call auto-refreshes via stored refresh token; if it returns
  "access expired", reconnect Drive in the Integrations panel.
- **`drive_read:false` on a read request** → model re-listed instead of reading (the M6 regression);
  confirm the read tool was offered and the file name matched a cached listing entry.
