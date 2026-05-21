from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from packages.persistence.policies_repo import PoliciesRepository

router = APIRouter(tags=["policies"])

_policies_repo = PoliciesRepository()

_DEFAULT_POLICY: dict[str, Any] = {
    "budget_soft_limit_usd": 10.0,
    "budget_hard_limit_usd": 50.0,
    "budget_period": "session",
    "updated_by": None,
}


class PolicyUpdateBody(BaseModel):
    budget_soft_limit_usd: float | None = None
    budget_hard_limit_usd: float | None = None
    budget_period: str | None = None


@router.get("/api/v1/policies")
async def get_policies() -> JSONResponse:
    try:
        record = await _policies_repo.get_current()
    except NotImplementedError:
        return JSONResponse(status_code=200, content=_DEFAULT_POLICY)
    if record is None:
        return JSONResponse(status_code=200, content=_DEFAULT_POLICY)
    return JSONResponse(status_code=200, content=record)


@router.put("/api/v1/policies")
async def put_policies(body: PolicyUpdateBody) -> JSONResponse:
    return await _update_policy(body)


@router.get("/api/v1/settings/budgets")
async def get_budgets() -> JSONResponse:
    try:
        record = await _policies_repo.get_current()
    except NotImplementedError:
        return JSONResponse(status_code=200, content=_DEFAULT_POLICY)
    if record is None:
        return JSONResponse(status_code=200, content=_DEFAULT_POLICY)
    return JSONResponse(status_code=200, content=record)


@router.patch("/api/v1/settings/budgets")
async def patch_budgets(body: PolicyUpdateBody) -> JSONResponse:
    return await _update_policy(body)


async def _update_policy(body: PolicyUpdateBody) -> JSONResponse:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        current = await _policies_repo.get_current()
        if current is None:
            record = await _policies_repo.create({**_DEFAULT_POLICY, **updates})
        else:
            record_id = current.get("id") if isinstance(current, dict) else None
            if record_id is None:
                record = await _policies_repo.create({**_DEFAULT_POLICY, **updates})
            else:
                record = await _policies_repo.update(record_id, **updates)
    except NotImplementedError:
        return JSONResponse(status_code=200, content={**_DEFAULT_POLICY, **updates})
    return JSONResponse(status_code=200, content=record)
