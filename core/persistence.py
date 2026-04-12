"""
JSON state file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from .config import STATE_FILE
from .logging_setup import log

if TYPE_CHECKING:
    from .state import FolderState


def load_state() -> Dict:
    try:
        p = Path(STATE_FILE)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            log.info(f"State loaded from {STATE_FILE}")
            return data
    except Exception as exc:
        log.warning(f"Could not load state: {exc}")
    return {}


def save_state(states: List["FolderState"]):
    data = {}
    for s in states:
        with s._lock:
            data[s.mapping.label] = {
                "uploaded":     dict(s.uploaded),
                "handled_dirs": list(s.handled_dirs),
                "skipped_dirs": list(s.skipped_dirs),
            }
    try:
        os.makedirs(Path(STATE_FILE).parent, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning(f"Could not save state: {exc}")
