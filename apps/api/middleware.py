from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DevUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        if os.environ.get("APP_ENV") == "dev":
            request.state.user_id = "dev-user"
        return await call_next(request)  # type: ignore[operator, no-any-return]
