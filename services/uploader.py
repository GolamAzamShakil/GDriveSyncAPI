"""
rclone wrapper + parallel upload batch logic.
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from core.config import MAX_UPLOAD_WORKERS, RCLONE_EXE
from core.logging_setup import log
from core.state import PROGRESS, FolderState

if TYPE_CHECKING:
    pass

_CF_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def _run_rclone(cmd: List[str], label: str, description: str) -> bool:
    log.info(f"[{label}] ↑ {description}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=_CF_NO_WINDOW,
        )
        if result.returncode == 0:
            log.info(f"[{label}] ✓ {description}")
            return True
        log.error(
            f"[{label}] ✗ rclone rc={result.returncode}: "
            f"{result.stderr.strip()}"
        )
    except subprocess.TimeoutExpired:
        log.error(f"[{label}] ✗ Timed out: {description}")
    except FileNotFoundError:
        log.error(f"rclone not found at: {RCLONE_EXE}")
    except Exception as exc:
        log.exception(f"[{label}] ✗ Unexpected: {exc}")
    return False

def _dest_for_file(local_path: str, base_path: str, rclone_dest: str) -> str:
    rel_par = Path(local_path).relative_to(Path(base_path)).parent
    return (
        rclone_dest
        if str(rel_par) == "."
        else f"{rclone_dest}/{rel_par.as_posix()}"
    )


def _parent_dest(folder_path: str, base_path: str, rclone_dest: str) -> str:
    parent = Path(folder_path).parent
    rel    = parent.relative_to(Path(base_path))
    return rclone_dest if str(rel) == "." else f"{rclone_dest}/{rel.as_posix()}"

def upload_one_file(local_path: str, state: FolderState) -> bool:
    p = Path(local_path)
    if not p.is_file():
        return False
    dest = _dest_for_file(local_path, state.mapping.local_path, state.mapping.rclone_dest)
    return _run_rclone(
        [RCLONE_EXE, "copy", str(p), dest, "--log-level", "ERROR"],
        state.mapping.label,
        f"{p.name}  →  {dest}",
    )

def upload_folder_with_name(folder_path: str, state: FolderState) -> bool:
    p    = Path(folder_path)
    rel  = p.relative_to(Path(state.mapping.local_path))
    dest = f"{state.mapping.rclone_dest}/{rel.as_posix()}"
    return _run_rclone(
        [RCLONE_EXE, "copy", str(p), dest, "--log-level", "ERROR"],
        state.mapping.label,
        f"[folder] {p.name}/  →  {dest}/",
    )


def upload_folder_contents(folder_path: str, parent_dest: str, state: FolderState) -> bool:
    p = Path(folder_path)
    return _run_rclone(
        [RCLONE_EXE, "copy", str(p), parent_dest, "--log-level", "ERROR"],
        state.mapping.label,
        f"[contents] {p.name}/  →  {parent_dest}/",
    )


# parallel batch

def upload_batch(files: List[Tuple[Path, float]], state: FolderState) -> None:
    """Upload a list of (Path, mtime) in parallel, tracking PROGRESS."""
    if not files:
        return

    PROGRESS.start(len(files))

    def worker(item: Tuple[Path, float]):
        f, mtime = item
        try:
            ok = upload_one_file(str(f), state)
            if ok:
                state.mark_uploaded(str(f), mtime)
        except Exception as exc:
            log.exception(f"[{state.mapping.label}] Worker error: {exc}")
        finally:
            PROGRESS.tick()

    with ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS) as pool:
        futures = [pool.submit(worker, item) for item in files]
        for _ in as_completed(futures):
            pass
