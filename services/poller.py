"""
Scan / poll logic — detect new folders and changed files,
then hand off to the uploader.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Tuple

from core.config import SETTLE_SECONDS
from core.logging_setup import log
from core.persistence import save_state
from core.schedule import SCHEDULE
from core.state import (
    ALL_STATES,
    FolderState,
    _force_poll,
    _paused,
    _shutdown,
)
from services.dialog import CHOICE_CONTENTS, CHOICE_SKIP, CHOICE_WITH_FOLDER, ask_folder_choice
from services.uploader import upload_batch, upload_folder_contents, upload_folder_with_name

def _settled(path: str) -> bool:
    try:
        return (time.time() - Path(path).stat().st_mtime) >= SETTLE_SECONDS
    except OSError:
        return False


def _rel_key(p: Path, base: Path) -> str:
    return str(p.relative_to(base))


def _parent_dest(folder_path: str, base_path: str, rclone_dest: str) -> str:
    parent = Path(folder_path).parent
    rel    = parent.relative_to(Path(base_path))
    return rclone_dest if str(rel) == "." else f"{rclone_dest}/{rel.as_posix()}"


def _process_new_folder(folder_path: str, state: FolderState) -> None:
    rel_key = _rel_key(Path(folder_path), Path(state.mapping.local_path))
    if rel_key in state.handled_dirs or rel_key in state.skipped_dirs:
        return

    log.info(f"[{state.mapping.label}] New folder: {folder_path}")
    choice = ask_folder_choice(folder_path, state.mapping.label)

    if choice == CHOICE_WITH_FOLDER:
        log.info(f"[{state.mapping.label}] → Upload with folder name")
        upload_folder_with_name(folder_path, state)
        for f in Path(folder_path).rglob("*"):
            if f.is_file():
                try:
                    state.mark_uploaded(str(f), f.stat().st_mtime)
                except OSError:
                    pass

    elif choice == CHOICE_CONTENTS:
        p_dest = _parent_dest(
            folder_path, state.mapping.local_path, state.mapping.rclone_dest
        )
        log.info(f"[{state.mapping.label}] → Upload contents into {p_dest}")
        upload_folder_contents(folder_path, p_dest, state)
        for f in Path(folder_path).rglob("*"):
            if f.is_file():
                try:
                    state.mark_uploaded(str(f), f.stat().st_mtime)
                except OSError:
                    pass

    else:
        log.info(f"[{state.mapping.label}] → Skipped: {Path(folder_path).name}")
        state.skipped_dirs.add(rel_key)

    state.handled_dirs.add(rel_key)
    save_state(ALL_STATES)

def poll_once(state: FolderState) -> None:
    root = Path(state.mapping.local_path)
    if not root.exists():
        log.warning(f"[{state.mapping.label}] Watch folder missing: {root}")
        return

    # handle new folders breadth-first
    all_dirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
    )
    for d in all_dirs:
        rel_key = _rel_key(d, root)
        parts   = Path(rel_key).parts
        if any(
            str(Path(*parts[:i + 1])) in state.skipped_dirs
            for i in range(len(parts))
        ):
            continue
        if rel_key not in state.handled_dirs and rel_key not in state.skipped_dirs:
            _process_new_folder(str(d), state)

    # collect changed / new files
    to_upload: List[Tuple[Path, float]] = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        rel   = f.relative_to(root)
        parts = rel.parts
        if any(
            str(Path(*parts[:i + 1])) in state.skipped_dirs
            for i in range(len(parts) - 1)
        ):
            continue
        if not _settled(str(f)):
            continue
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        if not state.is_uploaded(str(f), mtime):
            to_upload.append((f, mtime))

    total = len(to_upload)
    if total:
        log.info(f"[{state.mapping.label}] {total} file(s) to upload")
        upload_batch(to_upload, state)
        save_state(ALL_STATES)
    else:
        log.debug(f"[{state.mapping.label}] No changes.")

def poll_coordinator(states: List[FolderState]) -> None:
    log.info("Poll coordinator started.")
    while not _shutdown.is_set():
        for _ in range(30):
            if _shutdown.is_set() or _force_poll.is_set():
                break
            time.sleep(1)

        if _shutdown.is_set():
            break

        forced = _force_poll.is_set()
        if forced:
            _force_poll.clear()
            SCHEDULE.reset_interval()
            log.info("Forced scan by user.")

        if not forced and not SCHEDULE.due():
            continue

        if not _paused.is_set():
            log.debug("Paused — skipping poll.")
            continue

        for state in states:
            try:
                poll_once(state)
            except Exception as exc:
                log.exception(f"[{state.mapping.label}] Poll error: {exc}")

    log.info("Poll coordinator stopped.")


def start_poll_coordinator(states: List[FolderState]) -> threading.Thread:
    t = threading.Thread(
        target=poll_coordinator,
        args=(states,),
        daemon=True,
        name="PollCoordinator",
    )
    t.start()
    return t
