"""
Shared, thread-safe runtime state objects.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

@dataclass
class FolderMapping:
    local_path:  str
    rclone_dest: str
    label:       str = ""

class Progress:
    """Thread-safe upload progress tracker."""

    def __init__(self):
        self._lock     = threading.Lock()
        self.active    = False
        self.uploaded  = 0
        self.total     = 0
        self.remaining = 0

    def start(self, total: int):
        with self._lock:
            self.active    = True
            self.uploaded  = 0
            self.total     = total
            self.remaining = total

    def tick(self):
        with self._lock:
            self.uploaded  += 1
            self.remaining  = max(0, self.total - self.uploaded)
            if self.uploaded >= self.total:
                self.active = False

    def snapshot(self) -> Tuple[bool, int, int, int]:
        with self._lock:
            return self.active, self.uploaded, self.total, self.remaining

    def pct(self) -> Optional[int]:
        active, up, tot, _ = self.snapshot()
        if not active or tot == 0:
            return None
        return int(up / tot * 100)

    def label_progress(self) -> Optional[str]:
        active, up, tot, _ = self.snapshot()
        if not active or tot == 0:
            return None
        pct = int(up / tot * 100)
        return f"↑ Uploading…  {pct}%  ({up}/{tot})"

    def label_remaining(self) -> str:
        _, _, _, rem = self.snapshot()
        return f"Queued: {rem} file(s)" if rem > 0 else "Queued: —"

    def has_remaining(self) -> bool:
        _, _, _, rem = self.snapshot()
        return rem > 0


PROGRESS = Progress()

_paused     = threading.Event()
_paused.set()

_shutdown   = threading.Event()
_force_poll = threading.Event()


def is_paused() -> bool:
    return not _paused.is_set()

def pause():
    _paused.clear()

def resume():
    _paused.set()

def request_force_poll():
    _force_poll.set()

def request_shutdown():
    _shutdown.set()
    _paused.set()

@dataclass
class FolderState:
    mapping:      FolderMapping
    uploaded:     Dict[str, float] = field(default_factory=dict)
    handled_dirs: Set[str]         = field(default_factory=set)
    skipped_dirs: Set[str]         = field(default_factory=set)
    _lock:        threading.Lock   = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    def mark_uploaded(self, path: str, mtime: float):
        with self._lock:
            self.uploaded[path] = mtime

    def is_uploaded(self, path: str, mtime: float) -> bool:
        with self._lock:
            return self.uploaded.get(path) == mtime

    def restore(self, saved: Dict):
        self.uploaded     = {k: float(v) for k, v in saved.get("uploaded", {}).items()}
        self.handled_dirs = set(saved.get("handled_dirs", []))
        self.skipped_dirs = set(saved.get("skipped_dirs", []))

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "label":        self.mapping.label,
                "local_path":   self.mapping.local_path,
                "rclone_dest":  self.mapping.rclone_dest,
                "uploaded_count": len(self.uploaded),
                "handled_dirs": list(self.handled_dirs),
                "skipped_dirs": list(self.skipped_dirs),
                "uploaded_files": [
                    {"path": k, "mtime": v}
                    for k, v in self.uploaded.items()
                ],
            }


ALL_STATES: List[FolderState] = []
_STATE_REGISTRY_LOCK = threading.Lock()
