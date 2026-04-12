"""
Sync control & live state:
  GET  /api/sync/state          — full snapshot (viewer+)
  POST /api/sync/pause          — pause syncing (admin)
  POST /api/sync/resume         — resume syncing (admin)
  POST /api/sync/scan           — trigger immediate scan (admin)
  GET  /api/sync/progress       — live upload progress (viewer+)
"""
from fastapi import APIRouter, Depends

from api.dependencies.auth import require_admin, require_viewer_or_above
from core.state import PROGRESS, is_paused, pause, request_force_poll, resume
from models.schemas import MessageResponse, ProgressResponse, SyncStateResponse

router = APIRouter(prefix="/sync", tags=["Sync Control"])


@router.get(
    "/state",
    response_model=SyncStateResponse,
    summary="Get current sync state snapshot",
)
def get_state(_user=Depends(require_viewer_or_above)):
    active, uploaded, total, remaining = PROGRESS.snapshot()
    return SyncStateResponse(
        paused           = is_paused(),
        poll_active      = False,
        upload_active    = active,
        upload_pct       = PROGRESS.pct(),
        upload_uploaded  = uploaded,
        upload_total     = total,
        upload_remaining = remaining,
    )


@router.post(
    "/pause",
    response_model=MessageResponse,
    summary="Pause the sync engine (admin only)",
)
def pause_sync(_user=Depends(require_admin)):
    if is_paused():
        return MessageResponse(message="Already paused")
    pause()
    return MessageResponse(message="Sync paused")


@router.post(
    "/resume",
    response_model=MessageResponse,
    summary="Resume the sync engine (admin only)",
)
def resume_sync(_user=Depends(require_admin)):
    if not is_paused():
        return MessageResponse(message="Already running")
    resume()
    return MessageResponse(message="Sync resumed")


@router.post(
    "/scan",
    response_model=MessageResponse,
    summary="Trigger an immediate scan (admin only)",
)
def force_scan(_user=Depends(require_admin)):
    request_force_poll()
    return MessageResponse(
        message="Scan queued",
        detail="Scan will start within 30 seconds",
    )


@router.get(
    "/progress",
    response_model=ProgressResponse,
    summary="Live upload progress",
)
def get_progress(_user=Depends(require_viewer_or_above)):
    active, uploaded, total, remaining = PROGRESS.snapshot()
    return ProgressResponse(
        active    = active,
        uploaded  = uploaded,
        total     = total,
        remaining = remaining,
        pct       = PROGRESS.pct(),
        label     = PROGRESS.label_progress(),
    )
