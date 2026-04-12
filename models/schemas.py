"""
request/response schemas for all API endpoints.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int

class IntervalSchedule(BaseModel):
    enabled: bool
    hours:   int = Field(ge=0)
    minutes: int = Field(ge=0, le=59)

    @field_validator("hours", "minutes", mode="before")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Must be non-negative")
        return v

class ClockSchedule(BaseModel):
    enabled: bool
    times:   List[str] = Field(
        description="HH:MM strings in 24-hour format",
        examples=[["09:00", "18:00"]],
    )

class ScheduleUpdateRequest(BaseModel):
    interval: Optional[IntervalSchedule] = None
    clock:    Optional[ClockSchedule]    = None

class IntervalDetail(BaseModel):
    enabled:         bool
    total_seconds:   int
    hours:           int
    minutes:         int
    next_in_seconds: Optional[int]

class ClockDetail(BaseModel):
    enabled: bool
    times:   List[str]

class ScheduleResponse(BaseModel):
    interval:        IntervalDetail
    clock:           ClockDetail
    countdown_label: str

class SyncStateResponse(BaseModel):
    paused:          bool
    poll_active:     bool
    upload_active:   bool
    upload_pct:      Optional[int]
    upload_uploaded: int
    upload_total:    int
    upload_remaining: int

class ProgressResponse(BaseModel):
    active:    bool
    uploaded:  int
    total:     int
    remaining: int
    pct:       Optional[int]
    label:     Optional[str]

class UploadedFile(BaseModel):
    path:  str
    mtime: float

class FolderSummary(BaseModel):
    label:          str
    local_path:     str
    rclone_dest:    str
    uploaded_count: int
    handled_dirs:   List[str]
    skipped_dirs:   List[str]

class UploadedFilesResponse(BaseModel):
    folders: List[FolderSummary]
    files:   List[UploadedFile]
    total:   int

class UploadedFilesFilter(BaseModel):
    label:      Optional[str]  = None
    path_like:  Optional[str]  = None
    limit:      int            = Field(default=100, ge=1, le=5000)
    offset:     int            = Field(default=0,   ge=0)

class LogResponse(BaseModel):
    lines: List[str]
    count: int
    level_filter: Optional[str]

class MessageResponse(BaseModel):
    message: str
    detail:  Optional[str] = None
