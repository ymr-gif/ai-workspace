from .crud import router as _crud_router
from .files import router as _files_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(_crud_router)
router.include_router(_files_router)
