"""
Shared, thread-safe API health state.
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class ApiStatus:
    """
    Tracks the running state of the embedded uvicorn server.

    States
    STARTING  — server thread launched, health probe not yet confirmed
    HEALTHY   — /health returned 200 within the last probe cycle
    UNHEALTHY — probe failed (crash, port conflict, etc.)
    STOPPED   — server was intentionally shut down
    """

    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"

    def __init__(self):
        self._lock = threading.Lock()
        self._state = self.STARTING
        self._host: str = "127.0.0.1"
        self._port: int = 8000
        self._last_ok: Optional[float] = None
        self._error: str = ""

    def set_healthy(self, host: str, port: int):
        with self._lock:
            self._state = self.HEALTHY
            self._host = host
            self._port = port
            self._last_ok = time.time()
            self._error = ""

    def set_unhealthy(self, reason: str = ""):
        with self._lock:
            self._state = self.UNHEALTHY
            self._error = reason

    def set_starting(self):
        with self._lock:
            self._state = self.STARTING
            self._error = ""

    def set_stopped(self):
        with self._lock:
            self._state = self.STOPPED

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def host(self) -> str:
        with self._lock:
            return self._host

    @property
    def port(self) -> int:
        with self._lock:
            return self._port

    @property
    def url(self) -> str:
        with self._lock:
            h = "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host
            return f"http://{h}:{self._port}"

    @property
    def docs_url(self) -> str:
        return self.url + "/docs"

    @property
    def is_healthy(self) -> bool:
        with self._lock:
            return self._state == self.HEALTHY

    def tray_status_line(self) -> str:
        """One-line summary shown in the tray menu."""
        with self._lock:
            s = self._state
            h = "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host
            addr = f"{h}:{self._port}"
            if s == self.HEALTHY:
                return f"✅  API running  —  {addr}"
            if s == self.STARTING:
                return f"⏳  API starting…  —  {addr}"
            if s == self.UNHEALTHY:
                short = (
                    (self._error[:40] + "…") if len(self._error) > 40 else self._error
                )
                return f"❌  API error  —  {short or addr}"
            return f"⏹  API stopped  —  {addr}"

    def tray_icon_color(self) -> str:
        """Icon colour reflects health state."""
        s = self.state
        if s == self.HEALTHY:
            return "#4CAF50"
        if s == self.STARTING:
            return "#2196F3"
        if s == self.UNHEALTHY:
            return "#F44336"
        return "#9E9E9E"


API_STATUS = ApiStatus()
