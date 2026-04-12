"""
Uploaded file inventory with filtering:
  GET  /api/uploads                    — paginated + filtered list (viewer+)
  GET  /api/uploads/folders            — folder-level summaries (viewer+)
  GET  /api/uploads/folders/{label}    — single folder detail (viewer+)
  DELETE /api/uploads/folders/{label}/skipped  — clear skip list (admin)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies.auth import require_admin, require_viewer_or_above
from core.state import ALL_STATES
from models.schemas import (
    FolderSummary,
    MessageResponse,
    UploadedFile,
    UploadedFilesResponse,
)

router = APIRouter(prefix="/uploads", tags=["Uploaded Files"])


def _all_files_flat(label: Optional[str], path_like: Optional[str]):
    """Yield (UploadedFile, folder_label) for every recorded upload."""
    for state in ALL_STATES:
        if label and state.mapping.label != label:
            continue
        with state._lock:
            items = list(state.uploaded.items())
        for path, mtime in items:
            if path_like and path_like.lower() not in path.lower():
                continue
            yield UploadedFile(path=path, mtime=mtime), state.mapping.label


@router.get(
    "",
    response_model=UploadedFilesResponse,
    summary="List all recorded uploads with optional filters",
)
def list_uploads(
    label:     Optional[str] = Query(None, description="Filter by folder label"),
    path_like: Optional[str] = Query(None, description="Substring match on file path"),
    limit:     int           = Query(100, ge=1, le=5000),
    offset:    int           = Query(0,   ge=0),
    _user                    = Depends(require_viewer_or_above),
):
    all_files = [f for f, _ in _all_files_flat(label, path_like)]
    total     = len(all_files)
    page      = all_files[offset: offset + limit]

    folders = [
        FolderSummary(
            label          = s.mapping.label,
            local_path     = s.mapping.local_path,
            rclone_dest    = s.mapping.rclone_dest,
            uploaded_count = len(s.uploaded),
            handled_dirs   = list(s.handled_dirs),
            skipped_dirs   = list(s.skipped_dirs),
        )
        for s in ALL_STATES
        if (label is None or s.mapping.label == label)
    ]

    return UploadedFilesResponse(folders=folders, files=page, total=total)


@router.get(
    "/folders",
    response_model=List[FolderSummary],
    summary="Folder-level summary for all watched paths",
)
def list_folders(_user=Depends(require_viewer_or_above)):
    return [
        FolderSummary(
            label          = s.mapping.label,
            local_path     = s.mapping.local_path,
            rclone_dest    = s.mapping.rclone_dest,
            uploaded_count = len(s.uploaded),
            handled_dirs   = list(s.handled_dirs),
            skipped_dirs   = list(s.skipped_dirs),
        )
        for s in ALL_STATES
    ]


@router.get(
    "/folders/{label}",
    response_model=FolderSummary,
    summary="Single folder detail",
)
def get_folder(label: str, _user=Depends(require_viewer_or_above)):
    for s in ALL_STATES:
        if s.mapping.label == label:
            return FolderSummary(
                label          = s.mapping.label,
                local_path     = s.mapping.local_path,
                rclone_dest    = s.mapping.rclone_dest,
                uploaded_count = len(s.uploaded),
                handled_dirs   = list(s.handled_dirs),
                skipped_dirs   = list(s.skipped_dirs),
            )
    raise HTTPException(404, f"Folder label '{label}' not found")


@router.delete(
    "/folders/{label}/skipped",
    response_model=MessageResponse,
    summary="Clear the skip list for a folder so those dirs can be re-evaluated (admin only)",
)
def clear_skipped(label: str, _user=Depends(require_admin)):
    for s in ALL_STATES:
        if s.mapping.label == label:
            with s._lock:
                count = len(s.skipped_dirs)
                s.skipped_dirs.clear()
            return MessageResponse(
                message=f"Cleared {count} skipped dir(s) for '{label}'"
            )
    raise HTTPException(404, f"Folder label '{label}' not found")
