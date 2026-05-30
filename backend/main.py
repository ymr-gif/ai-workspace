import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

import llm.client as llm_client
from api.admin import router as admin_router
from api.graph import router as graph_router
from api.compat import router as compat_router
from api.insights import router as insights_router
from api.workspaces import router as workspaces_router
from api.chat import router as chat_router
from api.conversations import router as conversations_router
from api.files import router as files_router
from api.memory import router as memory_router
from api.scheduled_prompts import router as scheduled_prompts_router
from api.system import router as system_router
from api.templates import router as templates_router
from api.tool_logs import router as tool_logs_router
from api.export import router as export_router
from api.search import router as search_router
from api.usage import router as usage_router
from auth import auth_router, invite_router
from config import REQUEST_TIMEOUT
from config import REDIS_URL
from core.arq_pool import init_arq_pool
from core.db import init_db
from core.logger import setup_logging
from core.redis_client import get_redis, init_redis
from observability.metrics_api import router as metrics_router

setup_logging()
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[startup] init db...")
    await init_db()

    logger.info("[startup] init redis...")
    try:
        init_redis()
        await get_redis().ping()
        logger.info("[startup] redis ready")
    except Exception as e:
        logger.error("[startup] redis failed: %s", e)

    logger.info("[startup] restore circuit state...")
    try:
        from llm.circuit_breaker import restore_circuit_state
        await restore_circuit_state()
    except Exception as e:
        logger.warning("[startup] circuit restore failed: %s", e)

    logger.info("[startup] init arq pool...")
    try:
        await init_arq_pool(REDIS_URL)
        logger.info("[startup] arq pool ready")
    except Exception as e:
        logger.error("[startup] arq pool failed: %s", e)

    logger.info("[startup] init http client...")
    llm_client.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    logger.info("[startup] probe models...")
    try:
        from api.system import probe_models_on_startup
        await probe_models_on_startup()
    except Exception as e:
        logger.warning("[startup] model probe failed: %s", e)

    logger.info("[startup] check embedding model...")
    try:
        from services.re_embed import check_and_queue_re_embed
        await check_and_queue_re_embed()
    except Exception as e:
        logger.error("[startup] re_embed check failed: %s", e)

    logger.info("[startup] init neo4j...")
    try:
        from core.neo4j_client import init_neo4j
        await init_neo4j()
    except Exception as e:
        logger.warning("[startup] neo4j unavailable: %s", e)

    logger.info("[startup] ready")

    yield

    logger.info("[shutdown] closing http client...")
    if llm_client.client:
        await llm_client.client.aclose()

    try:
        from core.neo4j_client import close_neo4j
        await close_neo4j()
    except Exception:
        pass

    logger.info("[shutdown] complete")


app = FastAPI(title="NIM LLM Router", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(compat_router)
app.include_router(insights_router)
app.include_router(files_router,         prefix="/files")
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(system_router)
app.include_router(tool_logs_router)
app.include_router(admin_router)
app.include_router(usage_router)
app.include_router(templates_router)
app.include_router(scheduled_prompts_router)
app.include_router(workspaces_router)
app.include_router(export_router)
app.include_router(search_router)
app.include_router(graph_router)
app.include_router(invite_router)

Instrumentator().instrument(app).expose(app, endpoint="/prometheus")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("[global_error] %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {"type": "internal_error", "message": "Internal server error"},
            "meta": {"request_id": getattr(request.state, "request_id", "unknown")},
        },
    )
