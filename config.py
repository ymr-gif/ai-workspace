"""
config.py
─────────
Central configuration for:
- API keys
- model routing
- logging
- database

NOTE: All os.getenv() calls live here exclusively.
      No other module should import os directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

# ── NVIDIA NIM ────────────────────────────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NIM_URL = os.getenv(
    "NIM_URL",
    "https://integrate.api.nvidia.com/v1/chat/completions"
)

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/nimrouter"
)

# ── Model routing ─────────────────────────────────────────────────────────────
MODELS = {
    "llama":     "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "coder":     "qwen/qwen2.5-coder-32b-instruct",
    "reasoning": "nvidia/llama-3.1-nemotron-70b-instruct",
}

# ── Reliability settings ──────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30    # seconds
MAX_RETRIES = 2         # retries per model
FALLBACK_ORDER = [
    "reasoning",
    "coder",
    "llama",
]

# ── Router prompt ─────────────────────────────────────────────────────────────
ROUTER_SYSTEM_PROMPT = """
You are a routing system.

Classify the user message and return ONLY ONE of these model IDs:

- {llama}
- {coder}
- {reasoning}

Rules:
- Coding → coder
- Complex reasoning → reasoning
- Everything else → llama

Return ONLY the model string.
""".format(**MODELS)

# ── Startup guards ────────────────────────────────────────────────────────────
# These run at import time so misconfiguration fails loudly before the
# server accepts any requests.

if not NVIDIA_API_KEY:
    raise RuntimeError(
        "NVIDIA_API_KEY is not set. "
        "Add it to your .env file before starting the server."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Add it to your .env file before starting the server. "
        "Expected format: postgresql+asyncpg://user:password@host:port/dbname"
    )