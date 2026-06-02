from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from packages.persistence.jobs_repo import JobsRepository

_log = structlog.get_logger(__name__)


def _build_tool_routes() -> dict[str, Any]:
    from packages.tools.forecast_tool import ForecastTool
    from packages.tools.optimizer_tool import OptimizerTool
    from packages.tools.simulation_tool import SimulationTool
    from packages.tools.train_forecast_tool import TrainForecastTool

    return {
        "simulate": SimulationTool,
        "optimize": OptimizerTool,
        "forecast": ForecastTool,
        "train_forecast": TrainForecastTool,
    }


def _instantiate_tool(job_type: str, tool_cls: Any) -> Any:
    """Instantiate a tool class, injecting required dependencies where needed.

    ForecastTool requires a Predictor — inject LinearRegressionPredictor with
    no db_session (falls back to empty history / zero prediction).  All other
    current tools accept zero constructor arguments.
    """
    if job_type == "forecast":
        from packages.prediction import LinearRegressionPredictor

        return tool_cls(predictor=LinearRegressionPredictor(db_session=None))
    return tool_cls()


def _extract_files(output: dict[str, Any]) -> list[dict[str, Any]]:
    """Pop and return the ``generated_files`` list from *output* if present.

    Mutates *output* in-place so the key is not forwarded to result_json.
    """
    files = output.pop("generated_files", None)
    if not isinstance(files, list):
        return []
    return files


def _parse_params(raw: Any) -> dict[str, Any]:
    """Ensure params_json is a dict.

    asyncpg returns JSONB columns as Python dicts, but may return a string on
    some driver versions.  Handle both cases defensively.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    _log.warning("params_json is neither dict nor JSON string; using empty params", raw_type=type(raw).__name__)
    return {}


async def execute_job(
    job_id: UUID,
    sse_queue: Any | None = None,
) -> dict[str, Any]:
    """Execute a job by *job_id*.

    Steps:
    1. Load the job row from the DB.
    2. Route by ``job_type`` to the appropriate tool class.
    3. Build a minimal ``ToolContext`` and call ``tool.handle(params, ctx)``.
    4. On success: update status to ``"completed"`` with the result, attach any
       output files, and push a ``job_completed`` SSE event.
    5. On failure: update status to ``"failed"`` with the error message and push
       a ``job_failed`` SSE event.

    Returns the updated job row dict.
    """
    repo = JobsRepository()
    job = await repo.get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    job_type: str = job["job_type"]
    params: dict[str, Any] = _parse_params(job.get("params_json"))

    routes = _build_tool_routes()
    tool_cls = routes.get(job_type)
    if tool_cls is None:
        raise ValueError(f"Unknown job_type: {job_type!r}")

    from packages.tools.base import ToolContext

    _role_by_type: dict[str, str] = {
        "simulate": "simulation_optimizer",
        "optimize": "simulation_optimizer",
        "forecast": "demand",
        "train_forecast": "demand",
    }
    ctx = ToolContext(
        session_id=job["session_id"] if job.get("session_id") else uuid4(),
        agent_step_id=uuid4(),
        specialist_role=_role_by_type.get(job_type, "simulation_optimizer"),
        actor="system",
        correlation_id=uuid4(),
        user_role="admin",
    )

    try:
        tool = _instantiate_tool(job_type, tool_cls)
        tool_result = await tool.handle(params, ctx)

        output: dict[str, Any] = dict(tool_result.output)
        files: list[dict[str, Any]] = _extract_files(output)

        updated = await repo.update_status(
            job_id=job_id,
            status="completed",
            result=output,
        )
        for f in files:
            await repo.add_file(
                job_id=job_id,
                file_name=f.get("file_name", "output"),
                file_size_bytes=f.get("file_size_bytes", 0),
                mime_type=f.get("mime_type", "application/octet-stream"),
                download_url=f.get("download_url", ""),
            )

        if sse_queue is not None:
            await sse_queue.put(
                {
                    "type": "job_completed",
                    "job_id": str(job_id),
                    "job_type": job_type,
                    "file_count": len(files),
                    "files": [
                        {
                            "file_name": f.get("file_name", ""),
                            "download_url": f.get("download_url", ""),
                        }
                        for f in files
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        _log.info("job completed", job_id=str(job_id), job_type=job_type)
        return updated

    except Exception as exc:
        _log.exception("job failed", job_id=str(job_id), job_type=job_type)
        updated = await repo.update_status(
            job_id=job_id,
            status="failed",
            error=str(exc),
        )
        if sse_queue is not None:
            await sse_queue.put(
                {
                    "type": "job_failed",
                    "job_id": str(job_id),
                    "job_type": job_type,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return updated
