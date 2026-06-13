"""Unit tests for the jobs router (T-025).

All repository calls are replaced with AsyncMock so no real DB is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from apps.api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


def _make_job(
    job_id: UUID | None = None,
    session_id: UUID | None = None,
    status: str = "completed",
    job_type: str = "forecast",
) -> dict:
    return {
        "id": job_id or uuid4(),
        "session_id": session_id or uuid4(),
        "status": status,
        "job_type": job_type,
        "created_at": _NOW,
        "completed_at": _NOW,
    }


def _make_file(job_id: UUID, file_id: UUID | None = None) -> dict:
    return {
        "id": file_id or uuid4(),
        "job_id": job_id,
        "file_name": "report.csv",
        "file_size_bytes": 1024,
        "mime_type": "text/csv",
        "download_url": "https://example.com/report.csv",
        "created_at": _NOW,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/jobs — list jobs
# ---------------------------------------------------------------------------


async def test_list_jobs_returns_items_and_no_cursor_when_under_limit() -> None:
    job = _make_job()
    file = _make_file(job["id"])

    with (
        patch(
            "apps.api.routers.jobs._jobs_repo.list_jobs",
            new_callable=AsyncMock,
            return_value=[job],
        ),
        patch(
            "apps.api.routers.jobs._jobs_repo.list_files",
            new_callable=AsyncMock,
            return_value=[file],
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs?limit=20")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["next_cursor"] is None


async def test_list_jobs_returns_cursor_when_page_is_full() -> None:
    """When the page is exactly *limit* items long, next_cursor equals the last item id."""
    limit = 2
    jobs = [_make_job() for _ in range(limit)]

    with (
        patch(
            "apps.api.routers.jobs._jobs_repo.list_jobs",
            new_callable=AsyncMock,
            return_value=jobs,
        ),
        patch(
            "apps.api.routers.jobs._jobs_repo.list_files",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs?limit={limit}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_cursor"] == str(jobs[-1]["id"])


async def test_list_jobs_second_page_cursor_is_last_item_of_first_page() -> None:
    """Verify that the cursor returned on page 1 equals the id of the last item."""
    limit = 3
    jobs = [_make_job() for _ in range(limit)]

    with (
        patch(
            "apps.api.routers.jobs._jobs_repo.list_jobs",
            new_callable=AsyncMock,
            return_value=jobs,
        ),
        patch(
            "apps.api.routers.jobs._jobs_repo.list_files",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs?limit={limit}")

    data = resp.json()
    assert data["next_cursor"] == str(jobs[2]["id"])


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id} — single job
# ---------------------------------------------------------------------------


async def test_get_job_returns_job_with_files() -> None:
    job = _make_job()
    file = _make_file(job["id"])

    with (
        patch(
            "apps.api.routers.jobs._jobs_repo.get_job",
            new_callable=AsyncMock,
            return_value=job,
        ),
        patch(
            "apps.api.routers.jobs._jobs_repo.list_files",
            new_callable=AsyncMock,
            return_value=[file],
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/{job['id']}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(job["id"])
    assert len(data["generated_files"]) == 1
    assert data["generated_files"][0]["file_name"] == "report.csv"


async def test_get_job_404_on_unknown_id() -> None:
    missing_id = uuid4()

    with patch(
        "apps.api.routers.jobs._jobs_repo.get_job",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/{missing_id}")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/files — flat file list
# ---------------------------------------------------------------------------


async def test_list_files_all_files_linked_to_valid_job_ids() -> None:
    job_ids = [uuid4(), uuid4()]
    files = [
        _make_file(job_ids[0]),
        _make_file(job_ids[0]),
        _make_file(job_ids[1]),
    ]

    with patch(
        "apps.api.routers.jobs._jobs_repo.list_all_files",
        new_callable=AsyncMock,
        return_value=files,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/files?limit=20")

    assert resp.status_code == 200
    data = resp.json()
    returned_job_ids = {item["job_id"] for item in data["items"]}
    assert returned_job_ids == {str(jid) for jid in job_ids}


async def test_list_files_returns_no_cursor_when_under_limit() -> None:
    job_id = uuid4()
    files = [_make_file(job_id)]

    with patch(
        "apps.api.routers.jobs._jobs_repo.list_all_files",
        new_callable=AsyncMock,
        return_value=files,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/files?limit=20")

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_cursor"] is None


async def test_list_files_returns_cursor_when_page_is_full() -> None:
    limit = 2
    job_id = uuid4()
    files = [_make_file(job_id) for _ in range(limit)]

    with patch(
        "apps.api.routers.jobs._jobs_repo.list_all_files",
        new_callable=AsyncMock,
        return_value=files,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/files?limit={limit}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_cursor"] == str(files[-1]["id"])


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/files/{file_id}/download — T-613
# ---------------------------------------------------------------------------


def _make_file_row(
    job_id: UUID | None = None,
    file_id: UUID | None = None,
    file_content: bytes = b"col1,col2\n1,2\n",
    mime_type: str = "text/csv",
    file_name: str = "report.csv",
) -> dict:
    return {
        "id": file_id or uuid4(),
        "job_id": job_id or uuid4(),
        "file_name": file_name,
        "file_size_bytes": len(file_content),
        "mime_type": mime_type,
        "download_url": "/api/v1/jobs/files/some-id/download",
        "file_content": file_content,
        "created_at": _NOW,
    }


async def test_download_file_streams_content_with_correct_headers() -> None:
    """download_file must return 200 with the binary content and Content-Disposition."""
    file_id = uuid4()
    content = b"a,b\n1,2\n"
    row = _make_file_row(file_id=file_id, file_content=content, file_name="out.csv")

    with patch(
        "apps.api.routers.jobs._jobs_repo.get_file",
        new_callable=AsyncMock,
        return_value=row,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 200
    assert resp.content == content
    assert "attachment" in resp.headers["content-disposition"]
    assert "out.csv" in resp.headers["content-disposition"]
    assert resp.headers["content-type"].startswith("text/csv")


async def test_download_file_returns_404_when_row_not_found() -> None:
    """download_file must return 404 when get_file returns None."""
    file_id = uuid4()

    with patch(
        "apps.api.routers.jobs._jobs_repo.get_file",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 404


async def test_download_file_returns_404_when_content_is_empty() -> None:
    """download_file must return 404 when file_content is empty bytes."""
    file_id = uuid4()
    row = _make_file_row(file_id=file_id, file_content=b"")

    with patch(
        "apps.api.routers.jobs._jobs_repo.get_file",
        new_callable=AsyncMock,
        return_value=row,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 404
