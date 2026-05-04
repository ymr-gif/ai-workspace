"""
config.py
─────────
Single source of truth for every environment variable and constant.
Both auth.py and router.py import from here — nothing reads os.getenv() anywhere else.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── NVIDIA NIM ────────────────────────────────────────────────────────────────
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
NIM_URL: str        = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY: str = os.getenv(
    "JWT_SECRET_KEY",
    "change-me-in-production-use-a-long-random-string",
)
JWT_ALGORITHM: str              = "HS256"
JWT_EXPIRE_MINUTES: int         = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# ── LLM model registry ────────────────────────────────────────────────────────
# All slugs verified against /available-models (May 2026).
MODELS: dict[str, str] = {
    "llama":    "meta/llama-3.1-8b-instruct",           # fast general chat
    "qwen":     "qwen/qwen2.5-coder-32b-instruct",      # coding / debugging
    "nemotron": "nvidia/llama-3.1-nemotron-nano-8b-v1", # structured reasoning
    "glm":      "z-ai/glm4.7",                          # deep analysis / long-form
}

ROUTER_SYSTEM_PROMPT: str = f"""\
You are a model-selection router.
Given a user message, output ONLY one of these exact strings — nothing else:
  {MODELS["llama"]}
  {MODELS["qwen"]}
  {MODELS["nemotron"]}
  {MODELS["glm"]}

Selection rules (apply in order):
1. Coding, debugging, scripts, programming tasks              → {MODELS["qwen"]}
2. Complex multi-step reasoning, deep analysis, long-form     → {MODELS["glm"]}
3. Explanations, essays, structured reasoning                 → {MODELS["nemotron"]}
4. Simple chat, greetings, casual conversation                → {MODELS["llama"]}

Return ONLY the model name. No explanation.\
"""