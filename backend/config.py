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

# ── Web search ────────────────────────────────────────────────────────────────
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
WEB_SEARCH_BACKEND = os.getenv("WEB_SEARCH_BACKEND", "searxng")
SEARXNG_URL        = os.getenv("SEARXNG_URL",        "http://searxng:8080")
TAVILY_API_KEY     = os.getenv("TAVILY_API_KEY", "")

# ── App settings ──────────────────────────────────────────────────────────────
USE_REDIS              = os.getenv("USE_REDIS", "false").lower() == "true"
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
    "meta/llama-3.1-8b-instruct":            131072,
    "deepseek-ai/deepseek-v4-flash":           32768,
    "meta/llama-3.3-70b-instruct":            131072,
    "meta/llama-3.2-90b-vision-instruct":     131072,
}
DEFAULT_CONTEXT_WINDOW = 131072

# ── Model pricing — verify at build.nvidia.com/explore/llm ───────────────────
# $/1M tokens: input and output rates
MODEL_PRICING: dict[str, dict[str, float]] = {
    "meta/llama-3.1-8b-instruct":             {"input": 0.10, "output": 0.10},
    "deepseek-ai/deepseek-v4-flash":           {"input": 0.20, "output": 0.60},
    "meta/llama-3.3-70b-instruct":             {"input": 0.77, "output": 0.77},
    "meta/llama-3.2-90b-vision-instruct":      {"input": 0.16, "output": 0.16},
}

# ── Startup guards ────────────────────────────────────────────────────────────
if not NVIDIA_API_KEY:
    raise RuntimeError("NVIDIA_API_KEY is not set. Add it to your .env file.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set. Add it to your .env file.")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. Add it to your .env file.")
