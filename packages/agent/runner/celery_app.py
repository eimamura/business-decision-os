from __future__ import annotations

import asyncio
import os
from typing import Any

from celery import Celery

_broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("bdos", broker=_broker, backend=_backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
)


def _run_async(coro: Any) -> Any:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(bind=True, name="bdos.run_simulation")  # type: ignore[untyped-decorator]
def run_simulation_task(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from packages.simulation import InventorySimulator, SimulationContext, SimulationInput

    sim_input = SimulationInput(
        sku_id=payload["sku_id"],
        order_qty=float(payload.get("order_qty", 0.0)),
        horizon_days=int(payload.get("horizon_days", 90)),
    )
    sim_ctx = SimulationContext(db_session=None)
    output = _run_async(InventorySimulator().run(sim_input, sim_ctx))
    result: dict[str, Any] = output.model_dump()
    return result


@celery_app.task(bind=True, name="bdos.run_optimization")  # type: ignore[untyped-decorator]
def run_optimization_task(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
    from packages.optimization import OptimizationContext, OptimizationInput, ReplenishmentOptimizer

    opt_input = OptimizationInput(
        sku_id=payload["sku_id"],
        moq=float(payload.get("moq", 100.0)),
        horizon_days=int(payload.get("horizon_days", 90)),
        max_stockout_days=int(payload.get("max_stockout_days", 30)),
    )
    opt_ctx = OptimizationContext(db_session=None)
    output = _run_async(ReplenishmentOptimizer().run(opt_input, opt_ctx))
    result: dict[str, Any] = output.model_dump()
    return result
