import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY    = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM     = "HS256"
def _int_env(key: str, default: int) -> int:
    val = os.getenv(key, str(default)).strip()
    try:
        return int(val)
    except ValueError:
        result = 1
        for part in val.split("*"):
            result *= int(part.strip())
        return result

JWT_EXPIRE_MINUTES = _int_env("JWT_EXPIRE_MINUTES", 60)

# ── NVIDIA NIM ────────────────────────────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NIM_URL           = os.getenv("NIM_URL",           "https://integrate.api.nvidia.com/v1/chat/completions")
NIM_EMBEDDING_URL = os.getenv("NIM_EMBEDDING_URL", "https://integrate.api.nvidia.com/v1/embeddings")

# ── Backend selection (NIM ⇄ self-hosted llama.cpp home server) ────────────────
# Default "nim" → behavior identical to today (fully inert). Flip to "homeserver"
# to repoint the app at the local llama.cpp/Mixtral stack. The override block below
# (run before the startup guards, so it is also re-applied on importlib.reload via
# POST /admin/env/reload — no restart) rewrites endpoints, collapses the three model
# roles to one Mixtral, sizes context to 32k, and relaxes the NVIDIA_API_KEY guard.
LLM_BACKEND = os.getenv("LLM_BACKEND", "nim").lower()   # "nim" | "homeserver"
HOMESERVER_CHAT_URL    = os.getenv("HOMESERVER_CHAT_URL",    "http://llamacpp:8080/v1/chat/completions")
HOMESERVER_EMBED_URL   = os.getenv("HOMESERVER_EMBED_URL",   "http://llamacpp-embed:8081/v1/embeddings")
HOMESERVER_MODEL       = os.getenv("HOMESERVER_MODEL",       "mixtral")            # llama.cpp --alias
HOMESERVER_EMBED_MODEL = os.getenv("HOMESERVER_EMBED_MODEL", "bge-large-en-v1.5")
HOMESERVER_CTX         = _int_env("HOMESERVER_CTX", 32768)

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL")

# ── Model routing ─────────────────────────────────────────────────────────────
MODELS = {
    "llama":     os.getenv("MODEL_LLAMA",     "meta/llama-3.1-8b-instruct"),
    "coder":     os.getenv("MODEL_CODER",     "deepseek-ai/deepseek-v4-flash"),
    "reasoning": os.getenv("MODEL_REASONING", "meta/llama-3.3-70b-instruct"),
}

MODEL_EMBEDDING   = os.getenv("MODEL_EMBEDDING",   "nvidia/nv-embedqa-e5-v5")
MODEL_VISION      = os.getenv("MODEL_VISION",      "meta/llama-3.2-90b-vision-instruct")
EMBEDDING_DIM     = int(os.getenv("EMBEDDING_DIM", "1024"))

# ── Reliability ───────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
# Streaming read-timeout = max wait for the FIRST token / gap between tokens.
# Must exceed slow-model time-to-first-token (70B + tool schemas) or the stream
# ReadTimeouts before any token, retries hit the same wall, and the turn falls
# through the circuit breaker to a faster model (deepseek). Separate from the 30s
# connect/write budget so a slow first token never masquerades as 70B being down.
STREAM_READ_TIMEOUT = int(os.getenv("STREAM_READ_TIMEOUT", 120))
# Two wall-clock bounds + one output-token ceiling. STREAM_READ_TIMEOUT above is a
# PER-CHUNK read timeout (resets on every token) — it cannot bound a model that
# trickles one token every N seconds instead of failing outright; these three close
# that gap. 0 (or negative) on any of them = disabled (escape hatch). Read as
# config.X at call time in llm/nim.py / llm/service/stream.py, never `from config
# import` — /admin/env/reload must reach them live (LLM_BACKEND invariant).
STREAM_TOTAL_TIMEOUT   = int(os.getenv("STREAM_TOTAL_TIMEOUT", 120))      # s, one call_stream connection (llm/nim.py)
STREAM_TURN_BUDGET     = int(os.getenv("STREAM_TURN_BUDGET", 300))        # s, whole turn incl. every tool iteration + fallback model (llm/service/stream.py)
STREAM_MAX_TURN_TOKENS = int(os.getenv("STREAM_MAX_TURN_TOKENS", 16000))  # accumulated output tokens across the whole turn (llm/service/stream.py)
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", 3))
FALLBACK_ORDER  = ["reasoning", "coder", "llama"]

# ── Per-model rate limits (req / 60s) — applied only on explicit model selection
MODEL_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "llama":     (_int_env("RATE_LIMIT_LLAMA",     15), 60),
    "coder":     (_int_env("RATE_LIMIT_CODER",     10), 60),
    "reasoning": (_int_env("RATE_LIMIT_REASONING",  5), 60),
}

# ── Observability / Redis Streams ─────────────────────────────────────────────
OBSERVABILITY_ENABLED   = os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true"
METRICS_STREAM          = os.getenv("METRICS_STREAM", "metrics_stream")
METRICS_CONSUMER_GROUP  = os.getenv("METRICS_CONSUMER_GROUP", "metrics_workers")
METRICS_STREAM_MAXLEN   = int(os.getenv("METRICS_STREAM_MAXLEN", 10000))
METRICS_BATCH_SIZE      = int(os.getenv("METRICS_BATCH_SIZE", 100))

# ── Metrics worker ────────────────────────────────────────────────────────────
METRICS_WORKER_BLOCK_MS    = int(os.getenv("METRICS_WORKER_BLOCK_MS", 5000))
METRICS_WORKER_IDLE_SLEEP  = float(os.getenv("METRICS_WORKER_IDLE_SLEEP", 0.5))

# ── Prometheus ────────────────────────────────────────────────────────────────
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
PROMETHEUS_HOST    = os.getenv("PROMETHEUS_HOST", "0.0.0.0")
PROMETHEUS_PORT    = int(os.getenv("PROMETHEUS_PORT", 9100))

# ── Neo4j (graph memory) ──────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://neo4j:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ── Storage ───────────────────────────────────────────────────────────────────
STORAGE_DIR = os.getenv("STORAGE_DIR", "storage/files")

# ── Backup ────────────────────────────────────────────────────────────────────
BACKUP_SCHEDULE = os.getenv("BACKUP_SCHEDULE", "0 2 * * *")

# ── Auth ──────────────────────────────────────────────────────────────────────
REQUIRE_INVITE = os.getenv("REQUIRE_INVITE", "false").lower() == "true"

# ── Digest / Email ───────────────────────────────────────────────────────────
DIGEST_ENABLED  = os.getenv("DIGEST_ENABLED",  "false").lower() == "true"
DIGEST_SCHEDULE = os.getenv("DIGEST_SCHEDULE", "0 8 * * 1")
SMTP_HOST       = os.getenv("SMTP_HOST", "")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME   = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM       = os.getenv("SMTP_FROM", "")
# Require STARTTLS on non-465 ports (fail-closed against capability-stripping downgrade).
# Set false ONLY for plain dev relays (MailHog) — never for a real provider.
SMTP_STARTTLS   = os.getenv("SMTP_STARTTLS", "true").lower() == "true"

# ── Web search ────────────────────────────────────────────────────────────────
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
WEB_SEARCH_BACKEND = os.getenv("WEB_SEARCH_BACKEND", "searxng")
SEARXNG_URL        = os.getenv("SEARXNG_URL",        "http://searxng:8080")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY", "")

# ── Image / CPU-OCR (Q2 #19) ──────────────────────────────────────────────────
IMAGE_OCR_ENABLED = os.getenv("IMAGE_OCR_ENABLED", "false").lower() == "true"

# ── Voice / STT (Phase 1a — #20 Voice Input) ─────────────────────────────────
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "false").lower() == "true"
ASR_BACKEND   = os.getenv("ASR_BACKEND", "stub")
ASR_MODEL     = os.getenv("ASR_MODEL", "base.en")
ASR_LANGUAGE  = os.getenv("ASR_LANGUAGE", "")

# ── App settings ──────────────────────────────────────────────────────────────
USE_REDIS              = os.getenv("USE_REDIS", "false").lower() == "true"

# ── Memory write lock (inert switch — #21 Horizontal Scaling) ───────
# "pg" = pg_advisory_xact_lock (current behavior, default, zero change).
# "redis" = Redis SET NX + Lua compare-del (distributed-replica-safe).
# Toggleable live via /admin/env/reload (same pattern as LLM_BACKEND).
MEMORY_LOCK_BACKEND = os.getenv("MEMORY_LOCK_BACKEND", "pg").lower()
MEMORY_LOCK_TTL     = int(os.getenv("MEMORY_LOCK_TTL", "30"))
MEMORY_LOCK_WAIT    = int(os.getenv("MEMORY_LOCK_WAIT", "5"))
AI_TIMEOUT             = int(os.getenv("AI_TIMEOUT", 10))
MAX_CONCURRENT_REQUESTS = min(int(os.getenv("MAX_CONCURRENT_REQUESTS", 10)), 50)
LOG_LEVEL              = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT             = os.getenv("LOG_FORMAT", "json")

# ── Router system prompt ──────────────────────────────────────────────────────
ROUTER_SYSTEM_PROMPT = (
    "You are a routing system. Classify the user message and return ONLY ONE "
    "model ID from: {llama}, {coder}, {reasoning}. "
    "Coding → coder. Complex reasoning → reasoning. Everything else → llama."
).format(**MODELS)

# ── Context window sizes per model ───────────────────────────────────────────
CONTEXT_WINDOWS: dict[str, int] = {
    "meta/llama-3.1-8b-instruct":               131072,
    "deepseek-ai/deepseek-v4-flash":              32768,
    "meta/llama-3.3-70b-instruct":               131072,
    "meta/llama-3.2-90b-vision-instruct":        131072,
    "nvidia/llama-3.3-nemotron-super-49b-v1":    131072,
    "openai/gpt-oss-120b":                       131072,
}
DEFAULT_CONTEXT_WINDOW = 131072

# ── Model pricing — verify at build.nvidia.com/explore/llm ───────────────────
# $/1M tokens: input and output rates
MODEL_PRICING: dict[str, dict[str, float]] = {
    "meta/llama-3.1-8b-instruct":               {"input": 0.10, "output": 0.10},
    "deepseek-ai/deepseek-v4-flash":             {"input": 0.20, "output": 0.60},
    "meta/llama-3.3-70b-instruct":               {"input": 0.77, "output": 0.77},
    "meta/llama-3.2-90b-vision-instruct":        {"input": 0.16, "output": 0.16},
    "nvidia/llama-3.3-nemotron-super-49b-v1":    {"input": 0.10, "output": 0.40},
    "openai/gpt-oss-120b":                       {"input": 0.05, "output": 0.15},
}

# ── Notifications / Web Push (Phase 3c) ──────────────────────────────────────
VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT     = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
NOTIFICATION_RATE_LIMIT = int(os.getenv("NOTIFICATION_RATE_LIMIT", "5"))     # max per window
NOTIFICATION_RATE_WINDOW = int(os.getenv("NOTIFICATION_RATE_WINDOW", "60"))  # seconds

# ── External integrations (OAuth 2.0) ──────────────────────────────────────────
INTEGRATION_SECRET       = os.getenv("INTEGRATION_SECRET", "")
INTEGRATION_REDIRECT_BASE = os.getenv("INTEGRATION_REDIRECT_BASE", "http://localhost:8000")
GOOGLE_CLIENT_ID         = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET     = os.getenv("GOOGLE_CLIENT_SECRET", "")
NOTION_CLIENT_ID         = os.getenv("NOTION_CLIENT_ID", "")
NOTION_CLIENT_SECRET     = os.getenv("NOTION_CLIENT_SECRET", "")
GITHUB_CLIENT_ID         = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET     = os.getenv("GITHUB_CLIENT_SECRET", "")

# ── Runtime-configurable connector exposure (QUEUE Q0.6) ──────────────────────
# CSV of connector_type values ("google_drive,google_calendar,gmail") the UI should
# offer an OAuth button for. Empty (default) = every connector stays stubbed. Served
# via GET /api/integrations/available and read as config.ENABLED_CONNECTOR_TYPES at
# request time, so flipping it + POST /admin/env/reload exposes connectors with NO
# frontend rebuild — a Vite import.meta.env var is inlined at BUILD time and would
# not achieve that. Does NOT deactivate existing ExternalSource rows.
ENABLED_CONNECTOR_TYPES = [
    t.strip() for t in os.getenv("ENABLED_CONNECTOR_TYPES", "").split(",") if t.strip()
]

# ── Home-server override (applied when LLM_BACKEND="homeserver") ───────────────
# Placed after all base defs and before the guards so it rewrites the model/context
# tables and is re-applied verbatim on importlib.reload (runtime toggle, no restart).
# Inert when LLM_BACKEND="nim" (the default).
if LLM_BACKEND == "homeserver":
    NIM_URL                = HOMESERVER_CHAT_URL
    NIM_EMBEDDING_URL      = HOMESERVER_EMBED_URL
    MODELS                 = {role: HOMESERVER_MODEL for role in MODELS}   # collapse 3 roles → one Mixtral (Q-A5)
    MODEL_EMBEDDING        = HOMESERVER_EMBED_MODEL                        # 1024-d, no re-embed (Q-B1)
    CONTEXT_WINDOWS        = {HOMESERVER_MODEL: HOMESERVER_CTX}
    DEFAULT_CONTEXT_WINDOW = HOMESERVER_CTX                                # 32768 — budget allocator sizes correctly (Q-A3)
    # EMBEDDING_DIM stays 1024 in both modes → no migration / re-embed.
    # MODEL_RATE_LIMITS / MODEL_PRICING left keyed by NIM roles: cosmetic only,
    # router is telemetry-only in homeserver mode.

# ── Startup guards ────────────────────────────────────────────────────────────
# NIM key required only on the paid NIM backend; the LAN llama.cpp server needs none (Q-A6).
if LLM_BACKEND != "homeserver" and not NVIDIA_API_KEY:
    raise RuntimeError("NVIDIA_API_KEY is not set. Add it to your .env file.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set. Add it to your .env file.")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. Add it to your .env file.")
