from .router import router
from .stream import router as stream_router

router.include_router(stream_router)

__all__ = ["router"]
