import logging

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from config import MODELS
from observability.prom_metrics import CONTENT_TYPE_LATEST, export_metrics

router = APIRouter(tags=["system"])
logger = logging.getLogger("system")


class ResponseMeta(BaseModel):
    request_id: str


class SuccessResponse(BaseModel):
    success: bool = True
    data: dict
    meta: ResponseMeta


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict
    meta: ResponseMeta


@router.get("/health")
def health():
    return SuccessResponse(
        data={"status": "ok", "models": list(MODELS.keys())},
        meta=ResponseMeta(request_id="health"),
    )


@router.get("/metrics")
def metrics_endpoint():
    try:
        return Response(content=export_metrics(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        logger.exception("[metrics] export failed")
        return Response(content="# metrics export failed\n", media_type="text/plain", status_code=200)
