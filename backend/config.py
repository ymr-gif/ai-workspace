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
NIM_URL        = os.getenv("NIM_URL", "https://integrate.api.nvidia.com/v1/chat/completions")

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

# ── Reliability ───────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", 2))
FALLBACK_ORDER  = ["reasoning", "coder", "llama"]

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

# ── Storage ───────────────────────────────────────────────────────────────────
STORAGE_DIR = os.getenv("STORAGE_DIR", "storage/files")

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

# ── Startup guards ────────────────────────────────────────────────────────────
if not NVIDIA_API_KEY:
    raise RuntimeError("NVIDIA_API_KEY is not set. Add it to your .env file.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set. Add it to your .env file.")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. Add it to your .env file.")
