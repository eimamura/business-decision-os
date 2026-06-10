"""Regression tests for D-004.

D-004: POST /api/v1/approvals (create_approval) and POST /api/v1/approvals/{id}/decision
(post_decision) returned 500 because JSONResponse serialized raw repo rows that contain
uuid.UUID and datetime objects via stdlib json.dumps, which cannot handle those types.

Fix (T-488): fastapi.encoders.jsonable_encoder is now applied before passing to JSONResponse.

These tests stub the repo to return rows with real UUID and datetime values and assert:
1. The HTTP status code is correct (201 / 200).
2. The response body is valid JSON and can be parsed (asserting JSON-serializability).
3. The "id" field in the response is the stringified UUID.

Regression property: remove jsonable_encoder from the router and these tests fail with
500 (TypeError: Object of type UUID is not JSON serializable).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uuid_bearing_row(
    *,
    status: str = "pending",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a repo row that contains real UUID and datetime objects.

    This is the shape that asyncpg returns after an INSERT/UPDATE RETURNING *.
    stdlib json.dumps cannot serialise UUID or datetime — only jsonable_encoder
    converts them to str/ISO-8601 strings.
    """
    row: dict[str, Any] = {
        "id": uuid4(),                                     # real UUID — not str
        "session_id": uuid4(),                             # real UUID — not str
        "recommendation_id": uuid4(),                      # real UUID — not str
        "status": status,
        "reason": None,
        "actor": "test-user",
        "created_at": datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc),  # datetime
        "updated_at": datetime(2026, 6, 10, 12, 5, 0, tzinfo=timezone.utc),  # datetime
    }
    if extra:
        row.update(extra)
    return row


# ---------------------------------------------------------------------------
# T-490 test 1: create_approval — POST /api/v1/approvals
# ---------------------------------------------------------------------------


async def test_create_approval_with_uuid_row_returns_201_and_json_body() -> None:
    """POST /api/v1/approvals with a repo returning UUID/datetime values must return 201
    and a JSON-parseable body whose "id" is the stringified UUID.

    Regression property: this test fails (500) if jsonable_encoder is removed from
    the create_approval handler.
    """
    from httpx import ASGITransport, AsyncClient

    created_row = _make_uuid_bearing_row(status="pending")
    created_id: UUID = created_row["id"]

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.create = AsyncMock(return_value=created_row)

    mock_notifications_repo = MagicMock()
    mock_notifications_repo.create = AsyncMock(return_value={"id": uuid4()})

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    with (
        patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
        patch.object(approvals_module, "_notifications_repo", mock_notifications_repo),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/approvals",
                json={
                    "session_id": str(uuid4()),
                    "recommendation_id": str(uuid4()),
                    "reason": "regression test",
                },
                headers={"x-dev-user": "test-user"},
            )

    assert resp.status_code == 201
    # The body must be valid JSON (regression: without jsonable_encoder this is a 500)
    body = resp.json()
    assert body["id"] == str(created_id)


# ---------------------------------------------------------------------------
# T-490 test 2: post_decision — POST /api/v1/approvals/{id}/decision
# ---------------------------------------------------------------------------


async def test_post_decision_with_uuid_row_returns_200_and_json_body() -> None:
    """POST /api/v1/approvals/{id}/decision with repo returning UUID/datetime values
    must return 200 and a JSON-parseable body.

    Regression property: this test fails (500) if jsonable_encoder is removed from
    the post_decision handler.
    """
    from httpx import ASGITransport, AsyncClient

    approval_id = uuid4()
    get_row = _make_uuid_bearing_row(status="pending")
    # Override the id so it matches the path parameter
    get_row["id"] = approval_id

    updated_row = _make_uuid_bearing_row(status="approved")
    updated_row["id"] = approval_id
    updated_row["actor"] = "test-user"
    updated_id: UUID = updated_row["id"]

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=get_row)
    mock_approvals_repo.update = AsyncMock(return_value=updated_row)

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch.object(approvals_module, "can_execute", AsyncMock(return_value=True)),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                AsyncMock(),
            ),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approved", "reason": "regression test"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    # The body must be valid JSON (regression: without jsonable_encoder this is a 500)
    body = resp.json()
    assert body["id"] == str(updated_id)
