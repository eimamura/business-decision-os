from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobFileResponse(BaseModel):
    id: UUID
    job_id: UUID
    file_name: str
    file_size_bytes: int
    mime_type: str
    download_url: str
    created_at: datetime


class JobResponse(BaseModel):
    id: UUID
    session_id: UUID | None
    status: str
    job_type: str
    created_at: datetime
    completed_at: datetime | None
    generated_files: list[JobFileResponse] = []


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: UUID | None = None


class FileListResponse(BaseModel):
    items: list[JobFileResponse]
    next_cursor: UUID | None = None
