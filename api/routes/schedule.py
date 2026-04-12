"""
Schedule management:
  GET  /api/schedule            — read current schedule (viewer+)
  PUT  /api/schedule            — replace full schedule (admin)
  PATCH /api/schedule/interval  — update only interval block (admin)
  PATCH /api/schedule/clock     — update only clock block (admin)
  POST /api/schedule/reset      — reset interval countdown (admin)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.auth import require_admin, require_viewer_or_above
from core.schedule import SCHEDULE, _valid_hhmm
from models.schemas import (
    ClockSchedule,
    IntervalSchedule,
    MessageResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)

router = APIRouter(prefix="/schedule", tags=["Schedule"])


def _build_response() -> ScheduleResponse:
    d = SCHEDULE.to_dict()
    return ScheduleResponse(**d)


@router.get(
    "",
    response_model=ScheduleResponse,
    summary="Get current poll schedule",
)
def get_schedule(_user=Depends(require_viewer_or_above)):
    return _build_response()


@router.put(
    "",
    response_model=ScheduleResponse,
    summary="Replace the entire schedule (admin only)",
)
def update_schedule(body: ScheduleUpdateRequest, _user=Depends(require_admin)):
    if body.interval is not None:
        secs = body.interval.hours * 3600 + body.interval.minutes * 60
        if body.interval.enabled and secs < 60:
            raise HTTPException(400, "Interval must be at least 1 minute when enabled")
        SCHEDULE.set_interval(body.interval.enabled, secs)

    if body.clock is not None:
        bad = [t for t in body.clock.times if not _valid_hhmm(t)]
        if bad:
            raise HTTPException(400, f"Invalid HH:MM time(s): {bad}")
        SCHEDULE.set_clock(body.clock.enabled, body.clock.times)

    return _build_response()


@router.patch(
    "/interval",
    response_model=ScheduleResponse,
    summary="Update only the interval block (admin only)",
)
def patch_interval(body: IntervalSchedule, _user=Depends(require_admin)):
    secs = body.hours * 3600 + body.minutes * 60
    if body.enabled and secs < 60:
        raise HTTPException(400, "Interval must be at least 1 minute when enabled")
    SCHEDULE.set_interval(body.enabled, secs)
    return _build_response()


@router.patch(
    "/clock",
    response_model=ScheduleResponse,
    summary="Update only the clock block (admin only)",
)
def patch_clock(body: ClockSchedule, _user=Depends(require_admin)):
    bad = [t for t in body.times if not _valid_hhmm(t)]
    if bad:
        raise HTTPException(400, f"Invalid HH:MM time(s): {bad}")
    SCHEDULE.set_clock(body.enabled, body.times)
    return _build_response()


@router.post(
    "/reset",
    response_model=MessageResponse,
    summary="Reset the interval countdown to now + interval (admin only)",
)
def reset_interval(_user=Depends(require_admin)):
    SCHEDULE.reset_interval()
    return MessageResponse(
        message="Interval countdown reset", detail=SCHEDULE.countdown_label()
    )
