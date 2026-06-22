#!/usr/bin/env bash
#
# Post-deploy smoke test for the NIM AI Gateway.
# Drives the real end-to-end path against a running stack and exits non-zero on
# any failure — safe to run after every deploy (staging or prod).
#
# Usage:
#   ./smoke.sh [BASE_URL]
#   BASE_URL=https://my-host ./smoke.sh
#
# Env:
#   SMOKE_USER / SMOKE_PASS   seeded creds (default user / user-secret)
#
set -euo pipefail

BASE="${1:-${BASE_URL:-http://localhost:8000}}"
BASE="${BASE%/}"
USER_NAME="${SMOKE_USER:-user}"
USER_PASS="${SMOKE_PASS:-user-secret}"

pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

need() { command -v "$1" >/dev/null 2>&1 || fail "missing dependency: $1"; }
need curl; need python3

echo "smoke → $BASE  (user=$USER_NAME)"

# ── 1. health ───────────────────────────────────────────────────────────────────
step "1. health"
HEALTH="$(curl -fsS -m 15 "$BASE/health")" || fail "health endpoint unreachable"
echo "$HEALTH" | python3 -c '
import sys, json
h = json.load(sys.stdin)
assert h.get("status") == "ok", h
for dep in ("nim", "embedding", "redis", "db"):
    s = h["checks"][dep]["status"]
    assert s == "ok", f"{dep} unhealthy: {s}"
' || fail "health checks not all ok: $HEALTH"
pass "health ok (nim/embedding/redis/db)"

# ── 2. auth ─────────────────────────────────────────────────────────────────────
step "2. auth"
TOK="$(curl -fsS -m 15 -X POST "$BASE/auth/token" \
  -d "username=$USER_NAME&password=$USER_PASS" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')" \
  || fail "login failed for $USER_NAME"
[ -n "$TOK" ] || fail "empty access token"
AUTH="Authorization: Bearer $TOK"
pass "logged in, JWT acquired"
code="$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$BASE/conversations")"
[ "$code" = "401" ] || fail "unauthenticated /conversations returned $code (expected 401)"
pass "unauthenticated access rejected (401)"

# ── 3. file upload ──────────────────────────────────────────────────────────────
step "3. file upload"
TAG="SMOKE$(date +%s)"
FID="$(printf 'smoke note: the marker is %s\n' "$TAG" \
  | curl -fsS -m 30 -X POST "$BASE/files/upload" -H "$AUTH" \
      -F "file=@-;filename=smoke.txt;type=text/plain" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("id") or d.get("file_id") or "")')" \
  || fail "file upload failed"
[ -n "$FID" ] || fail "no file id returned"
pass "uploaded file $FID"

# ── 4. chat stream (live model) ─────────────────────────────────────────────────
step "4. chat stream"
SSE="$(mktemp)"
trap 'rm -f "$SSE"' EXIT
curl -fsS -N -m 90 -X POST "$BASE/chat/stream" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"message":"Reply with exactly one word: ping","temperature":0.9}' > "$SSE" \
  || fail "chat/stream request failed"
python3 - "$SSE" <<'PY' || fail "chat/stream did not produce a valid token+done sequence"
import sys, json
tokens, done = [], None
for line in open(sys.argv[1]):
    line = line.strip()
    if not line.startswith("data:"):
        continue
    try:
        e = json.loads(line[5:].strip())
    except json.JSONDecodeError:
        continue
    if e.get("type") == "token":
        tokens.append(e.get("content", ""))
    elif e.get("type") == "done":
        done = e
assert tokens and "".join(tokens).strip(), "no tokens streamed"
assert done is not None, "no done event"
for k in ("model", "cost_usd", "query_type", "conversation_id", "grounding"):
    assert k in done, f"done missing {k}"
print(f"    model={done['model']} cost=${done['cost_usd']:.6f} tokens={done.get('total_tokens')}")
PY
pass "streamed reply + complete done event"

# ── 5. metrics ──────────────────────────────────────────────────────────────────
step "5. metrics"
curl -fsS -m 15 "$BASE/metrics" | grep -q -E '^# (HELP|TYPE)' || fail "/metrics not exposing Prometheus output"
pass "/metrics exposed"

# ── 6. cleanup ──────────────────────────────────────────────────────────────────
step "6. cleanup"
code="$(curl -s -m 15 -o /dev/null -w '%{http_code}' -X DELETE "$BASE/files/$FID" -H "$AUTH")"
case "$code" in 200|204) pass "deleted smoke file" ;; *) printf '  (warn) delete returned %s\n' "$code" ;; esac

printf '\n\033[32mSMOKE PASSED\033[0m → %s\n' "$BASE"
