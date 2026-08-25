"""P103-B-04 integration test — T-620 (file download endpoint, real DB).

Tests the full path: add a job_files row via jobs_repo.add_file() against a
real PostgreSQL database, then hit GET /api/v1/jobs/files/{file_id}/download
via httpx ASGI transport and assert the response.

Requires:
    DATABASE_URL set (e.g. from .env)
    running PostgreSQL with the schema migrated

Run:
    DATABASE_URL=... uv run pytest tests/integration/test_p103_b04_file_download.py -v
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool so each test gets a fresh event-loop bound pool."""
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ---------------------------------------------------------------------------
# T-620 — Integration test: download endpoint (real DB)
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_download_file_returns_200_with_csv_bytes() -> None:
    """add_file with real DB rows, then download returns 200 with matching CSV bytes."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    from packages.persistence.jobs_repo import JobsRepository

    csv_content = b"sku_id,units\nSKU-001,10\n"
    file_name = "test_output.csv"
    file_id = uuid4()
    job_id = uuid4()

    repo = JobsRepository()

    # Insert a jobs row first so the FK constraint on job_files is satisfied.
    # Use the jobs table directly via the pool.
    from packages.persistence.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, status, job_type, params_json, created_at)
            VALUES ($1, 'completed', 'simulate', '{}', now())
            """,
            job_id,
        )

    # Insert the file row with file_content.
    await repo.add_file(
        job_id=job_id,
        file_name=file_name,
        file_size_bytes=len(csv_content),
        mime_type="text/csv",
        download_url=f"/api/v1/jobs/files/{file_id}/download",
        file_content=csv_content,
        file_id=file_id,
    )

    # Call the download endpoint via ASGI transport (no live server needed).
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 200
    assert resp.content == csv_content
    assert "attachment" in resp.headers["content-disposition"]
    assert file_name in resp.headers["content-disposition"]
    assert resp.headers["content-type"].startswith("text/csv")


@_SKIP_NO_DB
async def test_download_file_returns_404_when_content_is_empty() -> None:
    """add_file with empty file_content bytes → download returns 404."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    from packages.persistence.jobs_repo import JobsRepository

    file_id = uuid4()
    job_id = uuid4()

    # Insert the jobs row first.
    from packages.persistence.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, status, job_type, params_json, created_at)
            VALUES ($1, 'completed', 'simulate', '{}', now())
            """,
            job_id,
        )

    # Insert the file row with empty file_content.
    repo = JobsRepository()
    await repo.add_file(
        job_id=job_id,
        file_name="empty.csv",
        file_size_bytes=0,
        mime_type="text/csv",
        download_url=f"/api/v1/jobs/files/{file_id}/download",
        file_content=b"",
        file_id=file_id,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 404


@_SKIP_NO_DB
async def test_download_file_returns_404_for_nonexistent_file_id() -> None:
    """A file_id that does not exist in job_files → 404."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app

    nonexistent_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/jobs/files/{nonexistent_id}/download")

    assert resp.status_code == 404


@_SKIP_NO_DB
async def test_download_file_content_disposition_contains_file_name() -> None:
    """Content-Disposition header must contain the stored file_name verbatim."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    from packages.persistence.jobs_repo import JobsRepository

    file_name = "simulation_result.csv"
    file_id = uuid4()
    job_id = uuid4()

    from packages.persistence.db import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, status, job_type, params_json, created_at)
            VALUES ($1, 'completed', 'simulate', '{}', now())
            """,
            job_id,
        )

    repo = JobsRepository()
    csv_content = b"sku,qty\nA,10\n"
    await repo.add_file(
        job_id=job_id,
        file_name=file_name,
        file_size_bytes=len(csv_content),
        mime_type="text/csv",
        download_url=f"/api/v1/jobs/files/{file_id}/download",
        file_content=csv_content,
        file_id=file_id,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/jobs/files/{file_id}/download")

    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert file_name in disposition, (
        f"Expected '{file_name}' in Content-Disposition; got: {disposition!r}"
    )
