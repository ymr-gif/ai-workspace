from .ingest import router as _ingest_router
from .router import router  # base router; owns the empty-path list_files route
from .stream import router as _stream_router
from .versions import router as _versions_router
from .workspaces import router as _workspaces_router

# Include sub-routers (all have non-empty paths, no FastAPI empty-path conflict)
router.include_router(_ingest_router)
router.include_router(_workspaces_router)
router.include_router(_versions_router)
router.include_router(_stream_router)

__all__ = ["router"]
