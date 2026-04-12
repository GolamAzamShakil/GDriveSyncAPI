"""
All user-editable configuration constants.
Edit only this file for day-to-day tuning.
"""
from __future__ import annotations

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Add it to your .env file."
        )
    return val


RCLONE_EXE = _require_env("RCLONE_EXE")
LOG_FILE = _require_env("LOG_FILE")
STATE_FILE = _require_env("STATE_FILE")

ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")
VIEWER_PASSWORD = _require_env("VIEWER_PASSWORD")

LOG_MAX_MB  = int(os.environ.get("LOG_MAX_MB",  "5"))
LOG_BACKUPS = int(os.environ.get("LOG_BACKUPS", "3"))

MAX_UPLOAD_WORKERS = int(os.environ.get("MAX_UPLOAD_WORKERS", "3"))
SETTLE_SECONDS     = int(os.environ.get("SETTLE_SECONDS", "30"))
DIALOG_TIMEOUT     = int(os.environ.get("DIALOG_TIMEOUT", "60"))

DEFAULT_INTERVAL_ENABLED = True
DEFAULT_INTERVAL_HOURS   = 5
DEFAULT_CLOCK_ENABLED    = False
DEFAULT_CLOCK_TIMES: List[str] = ["09:00", "18:00"]

APP_NAME = "GDrive Sync API"
JWT_SECRET    = os.environ.get("JWT_SECRET", "changeme-use-a-long-random-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

USERS_DB: dict = {
    "admin": {"password": ADMIN_PASSWORD, "role": "admin"},
    "viewer": {"password": VIEWER_PASSWORD, "role": "viewer"},
}

CORS_ORIGINS: List[str] = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

def _build_folder_mappings() -> "List":
    from core.state import FolderMapping
    return [
        FolderMapping(
            local_path  = r"H:\myDrive\uploadSync\rclone\esratGdrive\Documents",
            rclone_dest = "11esrat11Gdrive:rclone/Documents",
            label       = "GdriveDocuments",
        ),
        FolderMapping(
            local_path  = r"H:\myDrive\uploadSync\rclone\esratGdrive\Photos",
            rclone_dest = "11esrat11Gdrive:rclone/Photos",
            label       = "GdrivePhotos",
        ),
    ]

FOLDER_MAPPINGS = _build_folder_mappings()
