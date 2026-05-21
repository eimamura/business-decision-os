from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from packages.persistence.notifications_repo import NotificationsRepository

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

_notifications_repo = NotificationsRepository()


@router.get("")
async def list_notifications(
    x_dev_user: str | None = Header(default=None),
) -> JSONResponse:
    try:
        records = await _notifications_repo.list(user_id=x_dev_user, read=False)
    except NotImplementedError:
        return JSONResponse(status_code=200, content=[])
    return JSONResponse(status_code=200, content=records)
