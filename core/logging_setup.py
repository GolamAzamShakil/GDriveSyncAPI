"""
Centralised logger setup.
Exposes an in-memory ring-buffer handler.
"""
from __future__ import annotations

import collections
import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import List

from .config import LOG_BACKUPS, LOG_FILE, LOG_MAX_MB

APP_NAME = "GDriveSyncAPI"

_LOG_RING_SIZE = 500
_ring_lock     = threading.Lock()
_ring: collections.deque = collections.deque(maxlen=_LOG_RING_SIZE)


class _RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        line = self.format(record)
        with _ring_lock:
            _ring.append(line)


def get_recent_logs(n: int = 100, level: str | None = None) -> List[str]:
    """Return the last *n* log lines, optionally filtered by level keyword."""
    with _ring_lock:
        lines = list(_ring)
    if level:
        up = level.upper()
        lines = [l for l in lines if f"[{up}" in l or f" {up} " in l]
    return lines[-n:]

def get_logger(name: str = APP_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    os.makedirs(Path(LOG_FILE).parent, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_MB * 1024 * 1024,
        backupCount=LOG_BACKUPS,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    rh = _RingHandler()
    rh.setFormatter(fmt)
    logger.addHandler(rh)

    return logger


log = get_logger()
