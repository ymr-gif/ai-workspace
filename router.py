"""
router.py
─────────
FastAPI entry point

Responsibilities:
- HTTP layer only
- request_id tracking
- authentication
- response formatting

NO heavy AI logic here (lives in service.py)
"""

from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from auth import auth_router, get_current_user
from config import MODELS
from db import init_db
from service import generate_response

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("router")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] initializing database tables...")
    await init_db()
    logger.info("[startup] database ready")
    yield
    logger.info("[shutdown] cleanup complete")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="NIM LLM Router", lifespan=lifespan)


# ── Middleware: request_id ────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Mount auth router ─────────────────────────────────────────────────────────
app.include_router(auth_router)


# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    model_used: str
    response: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    rid = request.state.request_id

    logger.info(f"[chat] rid={rid} user={current_user['username']}")

    result = await generate_response(req.message, rid)

    return ChatResponse(
        model_used=result["model_used"],
        response=result["response"],
    )


@app.get("/health")
def health():
    return {"status": "ok", "models": MODELS}