"""
router.py
─────────
FastAPI application entry point.
Responsibilities:
  - Mount the auth router  (POST /auth/token, GET /auth/me)
  - NIM call helpers       (_extract_content, call_nim, route_message)
  - Protected chat route   (POST /chat)  🔒 JWT required
  - Public system routes   (GET /health, GET /available-models)

Run with:
    uvicorn router:app --reload
"""

from fastapi import Depends, FastAPI
from pydantic import BaseModel
import httpx

from auth import auth_router, get_current_user
from config import MODELS, NVIDIA_API_KEY, NIM_URL, ROUTER_SYSTEM_PROMPT

app = FastAPI(title="NIM LLM Router")

# Mount all /auth/* routes from auth.py
app.include_router(auth_router)

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    model_used: str
    response: str

# ── NIM helpers ───────────────────────────────────────────────────────────────
def _extract_content(data: dict) -> str | None:
    """Try every known NIM / OpenAI response shape. Returns text or None."""
    # Standard OpenAI shape
    try:
        c = data["choices"][0]["message"]["content"]
        if c is not None:
            return str(c)
    except (KeyError, IndexError, TypeError):
        pass
    # Streaming leftover shape
    try:
        c = data["choices"][0]["delta"]["content"]
        if c is not None:
            return str(c)
    except (KeyError, IndexError, TypeError):
        pass
    # Flat text field
    if isinstance(data.get("text"), str):
        return data["text"]
    return None


async def call_nim(model: str, messages: list[dict], *, max_tokens: int = 512) -> dict:
    """POST a chat completion request to the NVIDIA NIM endpoint."""
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(NIM_URL, headers=headers, json=payload)

    if resp.status_code != 200:
        print(f"[call_nim] {model} → HTTP {resp.status_code}: {resp.text}")
        return {"error": resp.text, "status_code": resp.status_code}

    data    = resp.json()
    content = _extract_content(data)
    if content is not None:
        return {"content": content}

    print(f"[call_nim] unrecognised response shape from {model}: {data}")
    return {"error": "Unexpected response format", "raw": data}


async def route_message(message: str) -> str:
    """Ask llama (fast/cheap) to classify the message and return the best model slug."""
    result = await call_nim(
        model=MODELS["llama"],
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user",   "content": message},
        ],
        max_tokens=32,
    )
    if "error" in result:
        print("[router] routing call failed — falling back to llama")
        return MODELS["llama"]

    chosen = result["content"].strip()
    if chosen not in set(MODELS.values()):
        print(f"[router] unknown model '{chosen}' — falling back to llama")
        return MODELS["llama"]

    print(f"[router] → {chosen}")
    return chosen

# ── Protected chat route ──────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),  # 🔒 JWT required
):
    print(f"[chat] user='{current_user['username']}' message='{req.message[:60]}'")
    model  = await route_message(req.message)
    result = await call_nim(model=model, messages=[{"role": "user", "content": req.message}])

    if "error" in result:
        return ChatResponse(model_used=model, response=f"[ERROR] {result['error']}")

    return ChatResponse(model_used=model, response=result["content"])

# ── Public system routes ──────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "models": MODELS}


@app.get("/available-models", tags=["system"])
async def available_models():
    """Lists every model slug your API key can use on NIM."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}"},
        )
    if resp.status_code != 200:
        return {"error": resp.text}
    return {"models": sorted(m["id"] for m in resp.json().get("data", []))}