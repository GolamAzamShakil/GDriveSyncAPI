"""
main.py
=======

Run in API-only mode:
    uvicorn main:app --host 0.0.0.0 --port 8000

Run with system tray (normal desktop usage):
    pythonw.exe main.py
    python main.py

"""

from __future__ import annotations

import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import router
from core.api_status import API_STATUS
from core.config import (
    APP_NAME,
    CORS_ORIGINS,
    FOLDER_MAPPINGS,
)
from core.logging_setup import log
from core.persistence import load_state, save_state
from core.state import ALL_STATES, FolderState, _shutdown, request_shutdown
from services.poller import start_poll_coordinator

import os

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))


def _start_health_probe(host: str, port: int) -> threading.Thread:
    """
    Polls GET /health every 10 s (with a 30 s startup grace period).
    Updates API_STATUS so the tray always reflects real server state.
    """
    probe_url = f"http://localhost:{port}/health"

    def probe_loop():
        # time to bind before first probe
        time.sleep(6)
        import urllib.request, urllib.error

        while not _shutdown.is_set():
            try:
                with urllib.request.urlopen(probe_url, timeout=4) as r:
                    if r.status == 200:
                        API_STATUS.set_healthy(host, port)
                    else:
                        API_STATUS.set_unhealthy(f"HTTP {r.status}")
            except urllib.error.URLError as exc:
                API_STATUS.set_unhealthy(str(exc.reason))
            except Exception as exc:
                API_STATUS.set_unhealthy(str(exc))
            
            for _ in range(10):
                if _shutdown.is_set():
                    break
                time.sleep(1)

        API_STATUS.set_stopped()
        log.info("Health probe stopped.")

    t = threading.Thread(target=probe_loop, daemon=True, name="HealthProbe")
    t.start()
    return t


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info(f"{APP_NAME} API starting | {len(FOLDER_MAPPINGS)} folder(s)")
    log.info("=" * 60)

    saved = load_state()
    states: List[FolderState] = []
    for m in FOLDER_MAPPINGS:
        import os; os.makedirs(m.local_path, exist_ok=True)
        s = FolderState(mapping=m)
        if m.label in saved:
            s.restore(saved[m.label])
            log.info(f"[{m.label}] State restored")
        states.append(s)

    ALL_STATES.clear()
    ALL_STATES.extend(states)

    # background poll coordinator
    poll_thread = start_poll_coordinator(states)

    log.info(f"{APP_NAME} API ready.")
    yield

    log.info("Shutting down…")
    request_shutdown()
    poll_thread.join(timeout=5)
    save_state(ALL_STATES)
    log.info(f"{APP_NAME} shut down cleanly.")


def create_app() -> FastAPI:
    application = FastAPI(
        title       = f"{APP_NAME} API",
        description = (
            "REST API for controlling and monitoring the GDrive Sync engine. "
            "Provides upload tracking, schedule management, sync control, "
            "and log access with role-based authentication."
        ),
        version  = "1.0.0",
        lifespan = lifespan,
        docs_url = "/docs",
        redoc_url= "/redoc",
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins     = CORS_ORIGINS,
        allow_credentials = True,
        allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers     = [
            "Authorization",
            "Content-Type",
            "Accept",
            "X-Requested-With",
            "X-Request-ID",
        ],
        expose_headers    = ["X-Request-ID", "X-Process-Time"],
        max_age           = 600,
    )

    # headers middleware
    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"]          = "no-store"
        return response

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        log.exception(f"Unhandled error on {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


    application.include_router(router)

    @application.get("/health", tags=["Health"])
    def health():
        return {"status": "ok", "service": APP_NAME}

    return application


app = create_app()


if __name__ == "__main__":
    log.info(f"Starting {APP_NAME}  host={API_HOST}  port={API_PORT}")
    API_STATUS.set_starting()

    def _run_api():
        try:
            uvicorn.run(
                "main:app",
                host=API_HOST,
                port=API_PORT,
                log_config=None,
                log_level="warning",
            )
        except Exception as exc:
            API_STATUS.set_unhealthy(str(exc))
            log.exception(f"uvicorn crashed: {exc}")

    api_thread = threading.Thread(target=_run_api, daemon=True, name="APIServer")
    api_thread.start()

    _start_health_probe(API_HOST, API_PORT)

    try:
        from services.tray import run_tray

        run_tray()
    except ImportError:
        log.warning("Tray not available — running headless.")
        try:
            while not _shutdown.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        request_shutdown()
        log.info("Main thread exiting.")


# combined tray + uvicorn entry point
# if __name__ == "__main__":
#     import uvicorn

#     # Run uvicorn in its own daemon thread so the tray can run on main
#     def _run_api():
#         uvicorn.run(
#             "main:app",
#             host="0.0.0.0",
#             port=8000,
#             log_level="info",
#         )

#     api_thread = threading.Thread(target=_run_api, daemon=True, name="APIServer")
#     api_thread.start()

#     # If you still want the system tray, uncomment:
#     # from services.tray import run_tray
#     # run_tray()

#     # Otherwise just block until shutdown
#     import time
#     try:
#         while not _shutdown.is_set():
#             time.sleep(1)
#     except KeyboardInterrupt:
#         request_shutdown()
