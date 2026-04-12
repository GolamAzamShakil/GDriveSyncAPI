"""
All route modules into a single versioned APIRouter.
"""
from fastapi import APIRouter

from api.routes.auth     import router as auth_router
from api.routes.logs     import router as logs_router
from api.routes.schedule import router as schedule_router
from api.routes.sync     import router as sync_router
from api.routes.uploads  import router as uploads_router

router = APIRouter(prefix="/api/gdrivesync")

router.include_router(auth_router)
router.include_router(sync_router)
router.include_router(schedule_router)
router.include_router(uploads_router)
router.include_router(logs_router)
