"""
Poll schedule — interval mode and clock mode.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import List, Set

from .config import (
    DEFAULT_CLOCK_ENABLED,
    DEFAULT_CLOCK_TIMES,
    DEFAULT_INTERVAL_ENABLED,
    DEFAULT_INTERVAL_HOURS,
)


def _valid_hhmm(s: str) -> bool:
    try:
        datetime.strptime(s, "%H:%M")
        return True
    except ValueError:
        return False


class PollSchedule:
    def __init__(self):
        self._lock             = threading.Lock()
        self.interval_enabled  = DEFAULT_INTERVAL_ENABLED
        self.interval_seconds  = int(DEFAULT_INTERVAL_HOURS * 3600)
        self.clock_enabled     = DEFAULT_CLOCK_ENABLED
        self.clock_times: List[str] = list(DEFAULT_CLOCK_TIMES)
        self._next_interval    = time.time() + self.interval_seconds
        self._fired_clock: Set[str] = set()

    def get(self):
        with self._lock:
            return (
                self.interval_enabled,
                self.interval_seconds,
                self.clock_enabled,
                list(self.clock_times),
            )

    def to_dict(self) -> dict:
        ie, isec, ce, ctimes = self.get()
        h, remainder = divmod(isec, 3600)
        m = remainder // 60
        with self._lock:
            secs_until_next = max(0, int(self._next_interval - time.time()))
        return {
            "interval": {
                "enabled":         ie,
                "total_seconds":   isec,
                "hours":           h,
                "minutes":         m,
                "next_in_seconds": secs_until_next if ie else None,
            },
            "clock": {
                "enabled": ce,
                "times":   ctimes,
            },
            "countdown_label": self.countdown_label(),
        }

    def set_interval(self, enabled: bool, seconds: int):
        with self._lock:
            self.interval_enabled = enabled
            self.interval_seconds = max(60, seconds)
            self._next_interval   = time.time() + self.interval_seconds

    def set_clock(self, enabled: bool, times: List[str]):
        with self._lock:
            self.clock_enabled = enabled
            self.clock_times   = [t.strip() for t in times if _valid_hhmm(t.strip())]

    def reset_interval(self):
        with self._lock:
            self._next_interval = time.time() + self.interval_seconds

    def due(self) -> bool:
        now = time.time()
        with self._lock:
            if self.interval_enabled and now >= self._next_interval:
                self._next_interval = now + self.interval_seconds
                return True
            if self.clock_enabled:
                now_dt  = datetime.now()
                hhmm    = now_dt.strftime("%H:%M")
                day_key = now_dt.strftime("%Y-%m-%d ") + hhmm
                if hhmm in self.clock_times and day_key not in self._fired_clock:
                    self._fired_clock.add(day_key)
                    today = now_dt.strftime("%Y-%m-%d")
                    self._fired_clock = {
                        k for k in self._fired_clock if k.startswith(today)
                    }
                    return True
        return False

    def countdown_label(self) -> str:
        parts = []
        with self._lock:
            if self.interval_enabled:
                secs = max(0, int(self._next_interval - time.time()))
                h, r = divmod(secs, 3600)
                m, s = divmod(r, 60)
                parts.append(f"Interval: {h:02d}:{m:02d}:{s:02d}")
            if self.clock_enabled and self.clock_times:
                now_hhmm = datetime.now().strftime("%H:%M")
                future   = [t for t in sorted(self.clock_times) if t > now_hhmm]
                nxt      = future[0] if future else (self.clock_times[0] + " (+1d)")
                parts.append(f"Clock: next {nxt}")
        return "  |  ".join(parts) if parts else "No schedule active"


SCHEDULE = PollSchedule()
