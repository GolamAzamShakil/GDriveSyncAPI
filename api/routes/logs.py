"""
Log access — admin only endpoints:
  GET /api/logs              — recent log lines from in-memory ring buffer
  GET /api/logs/file         — tail raw log file from disk (last N bytes)
  GET /api/logs/stream       — Server-Sent Events live log stream
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.dependencies.auth import require_admin
from core.config import LOG_FILE
from core.logging_setup import get_recent_logs
from models.schemas import LogResponse

router = APIRouter(prefix="/logs", tags=["Logs (Admin)"])


@router.get(
    "",
    response_model=LogResponse,
    summary="Fetch recent log lines from in-memory buffer (admin only)",
)
def get_logs(
    n:     int           = Query(100, ge=1, le=500, description="Number of lines to return"),
    level: Optional[str] = Query(None, description="Filter: DEBUG|INFO|WARNING|ERROR"),
    _user                = Depends(require_admin),
):
    lines = get_recent_logs(n=n, level=level)
    return LogResponse(lines=lines, count=len(lines), level_filter=level)


@router.get(
    "/file",
    summary="Tail the log file from disk (admin only)",
)
def tail_log_file(
    bytes_from_end: int = Query(8192, ge=256, le=524288,
                                description="How many bytes from end of file to read"),
    _user               = Depends(require_admin),
):
    p = Path(LOG_FILE)
    if not p.exists():
        raise HTTPException(404, f"Log file not found: {LOG_FILE}")
    size = p.stat().st_size
    read_start = max(0, size - bytes_from_end)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        f.seek(read_start)
        content = f.read()
    lines = content.splitlines()
    if read_start > 0 and lines:
        lines = lines[1:]   # drop potentially partial first line
    return {"lines": lines, "count": len(lines), "file": str(p)}


@router.get(
    "/stream",
    summary="Server-Sent Events stream of new log lines (admin only)",
    response_class=StreamingResponse,
)
async def stream_logs(_user=Depends(require_admin)):
    """
    Streams new log lines as SSE events.
    Connect with EventSource('/api/logs/stream') from the dashboard.
    """
    async def event_generator():
        seen = set()
        try:
            while True:
                lines = get_recent_logs(n=500)
                for line in lines:
                    if line not in seen:
                        seen.add(line)
                        payload = line.replace("\n", " ")
                        yield f"data: {payload}\n\n"
                
                yield ": keep-alive\n\n"
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
