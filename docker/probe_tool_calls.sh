#!/usr/bin/env bash
# Q1 tool_calls gate probe — does llama.cpp emit OpenAI `tool_calls` from the
# GGUF chat template? This is the highest-risk Home-Server Port gate and it is a
# template/server property, not a GPU one, so it can be validated CPU-side.
#
# Bring up a server first (CPU validation, no GPU):
#   docker compose -f docker/docker-compose.yml -f docker/docker-compose.homeserver.cpu.yml \
#     --profile homeserver up -d llamacpp
# ...or the real GPU box:
#   docker compose -f docker/docker-compose.yml --profile homeserver up -d llamacpp
#
# Then:  ./docker/probe_tool_calls.sh
#
# Env overrides:
#   BASE_URL   default http://localhost:8080   (llama.cpp OpenAI server)
#   MODEL      default mixtral                  (the --alias set in compose)
#   WAIT       default 120                      (secs to wait for /health on boot)
#
# Exit codes: 0 = PASS (tool_calls emitted) · 1 = FAIL (prose only → BUGS Q-A2
# prompt fallback) · 2 = ERROR (deps missing / server unreachable / bad response)

set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
MODEL="${MODEL:-mixtral}"
WAIT="${WAIT:-120}"

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

# ── deps ──────────────────────────────────────────────────────────────────────
for bin in curl jq; do
  command -v "$bin" >/dev/null 2>&1 || { red "missing dependency: $bin"; exit 2; }
done

# ── wait for /health ──────────────────────────────────────────────────────────
dim "Waiting for $BASE_URL/health (up to ${WAIT}s; model load can be slow)…"
deadline=$(( $(date +%s) + WAIT ))
until curl -fsS "$BASE_URL/health" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    red "server not healthy at $BASE_URL after ${WAIT}s"
    dim "is it up?  docker compose --profile homeserver ps"
    exit 2
  fi
  sleep 3
done
green "server healthy."

# ── probe ─────────────────────────────────────────────────────────────────────
read -r -d '' PAYLOAD <<JSON
{
  "model": "$MODEL",
  "messages": [
    {"role": "user", "content": "What is the weather in Paris right now? Use the tool."}
  ],
  "tools": [
    {"type": "function", "function": {
      "name": "get_weather",
      "description": "Get the current weather for a city.",
      "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name"}},
        "required": ["city"]
      }
    }}
  ],
  "tool_choice": "auto",
  "temperature": 0,
  "stream": false
}
JSON

dim "POST $BASE_URL/v1/chat/completions  (model=$MODEL)…"
RESP="$(curl -fsS "$BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' -d "$PAYLOAD" 2>/dev/null)"
if [ -z "$RESP" ]; then
  red "empty / failed response from server"
  exit 2
fi

if ! echo "$RESP" | jq -e . >/dev/null 2>&1; then
  red "response is not valid JSON:"
  echo "$RESP" | head -c 800; echo
  exit 2
fi

TOOL_CALLS="$(echo "$RESP" | jq -c '.choices[0].message.tool_calls // empty')"
FUNC="$(echo "$RESP"  | jq -r '.choices[0].message.tool_calls[0].function.name // empty')"
ARGS="$(echo "$RESP"  | jq -r '.choices[0].message.tool_calls[0].function.arguments // empty')"
CONTENT="$(echo "$RESP" | jq -r '.choices[0].message.content // empty')"

echo
if [ -n "$TOOL_CALLS" ] && [ "$TOOL_CALLS" != "null" ]; then
  green "✅ PASS — server emitted OpenAI tool_calls."
  echo "   function : $FUNC"
  echo "   arguments: $ARGS"
  if [ -n "$FUNC" ] && [ "$FUNC" != "get_weather" ]; then
    dim   "   note: function name != get_weather — sanity-check the template mapping."
  fi
  echo
  dim "Gate cleared. Run the full agent loop next (llm/nim.py + llm/service/stream.py)."
  exit 0
else
  red "❌ FAIL — no tool_calls; model answered as prose."
  echo "   content: $(echo "$CONTENT" | head -c 300)"
  echo
  dim "Per BUGS Q-A2: fall back to prompt-based tool calling."
  dim "Also confirm the server was started with --jinja (required for native tool templates)."
  exit 1
fi
