from .users import router as _users_router
from .audit import router as _audit_router
from .env import router as _env_router
from .system import router as _system_router
from .memory import router as _memory_router
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(_users_router)
router.include_router(_audit_router)
router.include_router(_env_router)
router.include_router(_system_router)
router.include_router(_memory_router)
