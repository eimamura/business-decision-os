from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from packages.persistence.jobs_repo import JobsRepository
from packages.schemas.jobs import (
    FileListResponse,
    JobFileResponse,
    JobListResponse,
    JobResponse,
)

router = APIRouter(prefix="/api/v1", tags=["jobs"])

_jobs_repo = JobsRepository()


def _to_job_response(job: dict[str, Any], files: list[dict[str, Any]]) -> JobResponse:
    raw_result = job.get("result_json")
    result_json: dict[str, object] | None = None
    if isinstance(raw_result, dict):
        result_json = raw_result
    elif isinstance(raw_result, str):
        import json as _json

        try:
            parsed = _json.loads(raw_result)
            result_json = parsed if isinstance(parsed, dict) else None
        except ValueError:
            result_json = None

    return JobResponse(
        id=job["id"],
        session_id=job.get("session_id"),
        status=job["status"],
        job_type=job["job_type"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        approval_id=job.get("approval_id"),
        result_json=result_json,
        generated_files=[JobFileResponse(**f) for f in files],
    )


def _to_file_response(f: dict[str, Any]) -> JobFileResponse:
    return JobFileResponse(
        id=f["id"],
        job_id=f["job_id"],
        file_name=f["file_name"],
        file_size_bytes=f["file_size_bytes"],
        mime_type=f["mime_type"],
        download_url=f["download_url"],
        created_at=f["created_at"],
    )


@router.get(
    "/jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_jobs(
    cursor: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    job_status: str | None = Query(default=None, alias="status"),
) -> JobListResponse:
    """Return a cursor-paginated list of jobs with their generated files."""
    try:
        rows = await _jobs_repo.list_jobs(cursor=cursor, limit=limit, status=job_status)
    except RuntimeError as exc:
        if "DATABASE_URL" in str(exc):
            return JobListResponse(items=[], next_cursor=None)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        )

    items: list[JobResponse] = []
    for row in rows:
        files = await _jobs_repo.list_files(job_id=row["id"])
        items.append(_to_job_response(row, files))

    next_cursor: UUID | None = None
    if len(rows) == limit:
        next_cursor = rows[-1]["id"]

    return JobListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job(job_id: UUID) -> JobResponse:
    """Return a single job by ID, including generated files."""
    try:
        row = await _jobs_repo.get_job(job_id)
    except RuntimeError as exc:
        if "DATABASE_URL" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        )

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    files = await _jobs_repo.list_files(job_id=job_id)
    return _to_job_response(row, files)


@router.get(
    "/files",
    response_model=FileListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_files(
    cursor: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> FileListResponse:
    """Return a cursor-paginated flat list of all generated files across jobs."""
    try:
        rows = await _jobs_repo.list_all_files(cursor=cursor, limit=limit)
    except RuntimeError as exc:
        if "DATABASE_URL" in str(exc):
            return FileListResponse(items=[], next_cursor=None)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        )

    items = [_to_file_response(r) for r in rows]

    next_cursor: UUID | None = None
    if len(rows) == limit:
        next_cursor = rows[-1]["id"]

    return FileListResponse(items=items, next_cursor=next_cursor)
