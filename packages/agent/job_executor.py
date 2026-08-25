from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from packages.agent.base import SpecialistRole
from packages.persistence.jobs_repo import JobsRepository

_log = structlog.get_logger(__name__)

VALID_JOB_TYPES: frozenset[str] = frozenset({
    "simulate",
    "inventory_simulation",
    "optimize",
    "forecast",
    "train_forecast",
})


async def _persist_report_message(session_id: Any | None, content: str) -> None:
    """Persist an assistant report message into the originating session (T-602).

    Uses DecisionSessionRepository.add_message — the same mechanism as normal
    replies in apps/api/routers/sessions.py — so the report renders on session reload.

    Silently skips if session_id is None or the DB write fails (best-effort).
    """
    if session_id is None:
        return
    try:
        from packages.persistence.sessions_repo import DecisionSessionRepository  # noqa: PLC0415
        await DecisionSessionRepository().add_message(
            str(session_id), role="assistant", content=content
        )
    except Exception as exc:  # noqa: BLE001 — soft-fail: report is best-effort
        _log.warning(
            "job report message persist failed (non-fatal)",
            session_id=str(session_id),
            error=str(exc),
        )


async def _sync_session_status(session_id: Any | None, status: str) -> None:
    """Best-effort decision_sessions terminal-status sync after a job finishes (D-026).

    On the approval path the session pauses as 'awaiting_input'; when the linked
    job reaches a terminal state the session must reach the contract-correct
    terminal state ('completed' on success, 'failed' on failure). Soft-fails so a
    status sync problem never fails an already-terminal job.
    """
    if session_id is None:
        return
    try:
        from packages.persistence.sessions_repo import DecisionSessionRepository  # noqa: PLC0415
        await DecisionSessionRepository().update_status(str(session_id), status)
    except Exception as exc:  # noqa: BLE001 — soft-fail: sync is best-effort
        _log.warning(
            "session terminal-status sync failed (non-fatal)",
            session_id=str(session_id),
            target_status=status,
            error=str(exc),
        )


async def _push_report_event(sse_queue: Any, session_id: Any | None, report: str) -> None:
    """Push a job_report SSE event so a live subscriber gets the report immediately (T-602).

    The event type ``job_report`` is a new additive type — it carries the assistant
    report text and session_id so the client can render it as an assistant message
    without waiting for the next page reload.
    """
    try:
        await sse_queue.put({
            "type": "job_report",
            "session_id": str(session_id) if session_id is not None else None,
            "content": report,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:  # noqa: BLE001 — soft-fail: SSE push is best-effort
        _log.warning(
            "job report SSE push failed (non-fatal)",
            session_id=str(session_id) if session_id is not None else None,
            error=str(exc),
        )


def _build_tool_routes() -> dict[str, Any]:
    from packages.tools.forecast_tool import ForecastTool
    from packages.tools.optimizer_tool import OptimizerTool
    from packages.tools.simulation_tool import SimulationTool
    from packages.tools.train_forecast_tool import TrainForecastTool

    return {
        "simulate": SimulationTool,
        "inventory_simulation": SimulationTool,
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
    _log.warning(
        "params_json is neither dict nor JSON string; using empty params",
        raw_type=type(raw).__name__,
    )
    return {}


def _build_completion_report(job_type: str, status: str, result: dict[str, Any] | None) -> str:
    """Build a short assistant report message for a completed or failed job.

    For a completed ``train_forecast`` job the report includes the trained model
    version and horizon so the human can verify what was trained.  Other job types
    get a generic success summary.  Failure reports include the error excerpt.
    """
    if status == "failed":
        error = result.get("error", "unknown error") if result else "unknown error"
        return (
            f"**Job report — {job_type} failed.**\n\n"
            f"The background job could not complete: {str(error)[:300]}"
        )
    # Completed
    if job_type == "train_forecast" and result:
        sku = result.get("sku_id", "unknown")
        model_ver = result.get("model_version", "unknown")
        horizon = result.get("horizon_days", "?")
        return (
            f"**Job report — train_forecast completed.**\n\n"
            f"SKU: {sku} | Model version: {model_ver} | Horizon: {horizon} days.\n"
            "Predictions have been updated in the database."
        )
    summary = str(result)[:200] if result else "no result data"
    return (
        f"**Job report — {job_type} completed.**\n\n"
        f"Result summary: {summary}"
    )


async def execute_job(
    job_id: UUID,
    sse_queue: Any | None = None,
) -> dict[str, Any]:
    """Execute a job by *job_id*.

    Steps:
    1. Load the job row from the DB.
    2. Transition status: pending_approval/queued → running.
    3. Route by ``job_type`` to the appropriate tool class.
    4. Build a minimal ``ToolContext`` and call ``tool.handle(params, ctx)``.
    5. On success: update status to ``"completed"`` with the result, attach any
       output files, push a ``job_completed`` SSE event, and persist an assistant
       report message into the originating session (T-602).
    6. On failure: update status to ``"failed"`` with the error message, push a
       ``job_failed`` SSE event, and persist an assistant failure report (T-602).

    The ``sse_queue`` parameter accepts either an ``asyncio.Queue`` or any object
    with a compatible ``put(event: dict) -> Awaitable`` method (e.g. a
    ``Broadcaster`` instance from ``apps.api.state``).

    Returns the updated job row dict.
    """
    repo = JobsRepository()
    job = await repo.get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    job_type: str = job["job_type"]
    params: dict[str, Any] = _parse_params(job.get("params_json"))
    session_id_val = job.get("session_id")

    routes = _build_tool_routes()
    tool_cls = routes.get(job_type)
    if tool_cls is None:
        raise ValueError(f"Unknown job_type: {job_type!r}")

    # Transition to running so monitoring can observe progress.
    await repo.update_status(job_id=job_id, status="running")

    from packages.tools.base import ToolContext

    _role_by_type: dict[str, SpecialistRole] = {
        "simulate": "simulation_optimizer",  # type: ignore[dict-item]
        "inventory_simulation": "simulation_optimizer",  # type: ignore[dict-item]
        "optimize": "simulation_optimizer",  # type: ignore[dict-item]
        "forecast": "data_engineer",  # type: ignore[dict-item]
        "train_forecast": "data_engineer",  # type: ignore[dict-item]
    }
    _specialist_role: SpecialistRole = _role_by_type.get(job_type, "simulation_optimizer")  # type: ignore[arg-type]
    effective_session_id = session_id_val if session_id_val is not None else uuid4()
    ctx = ToolContext(
        session_id=effective_session_id,
        agent_step_id=uuid4(),
        specialist_role=_specialist_role,
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
        # Pre-generate a file_id for each file so the download_url can reference
        # it before the INSERT; pass it through to repo.add_file to keep them in sync.
        enriched_files: list[dict[str, Any]] = []
        for f in files:
            file_id = uuid4()
            download_url = f"/api/v1/jobs/files/{file_id}/download"
            file_content: bytes = f.get("file_content", b"")
            if isinstance(file_content, str):
                file_content = file_content.encode()
            await repo.add_file(
                job_id=job_id,
                file_name=f.get("file_name", "output"),
                file_size_bytes=len(file_content) or f.get("file_size_bytes", 0),
                mime_type=f.get("mime_type", "application/octet-stream"),
                download_url=download_url,
                file_content=file_content,
                file_id=file_id,
            )
            enriched_files.append({**f, "download_url": download_url, "file_id": str(file_id)})

        if sse_queue is not None:
            await sse_queue.put(
                {
                    "type": "job_completed",
                    "job_id": str(job_id),
                    "job_type": job_type,
                    "file_count": len(enriched_files),
                    "files": [
                        {
                            "file_name": ef.get("file_name", ""),
                            "download_url": ef.get("download_url", ""),
                        }
                        for ef in enriched_files
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # T-602: persist assistant report message into the originating session
        report = _build_completion_report(job_type, "completed", output)
        await _persist_report_message(session_id_val, report)
        if sse_queue is not None:
            await _push_report_event(sse_queue, session_id_val, report)

        # D-026: session reaches its contract-correct terminal state after job execution
        await _sync_session_status(session_id_val, "completed")

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

        # T-602: persist failure report message into the originating session
        fail_report = _build_completion_report(job_type, "failed", {"error": str(exc)})
        await _persist_report_message(session_id_val, fail_report)
        if sse_queue is not None:
            await _push_report_event(sse_queue, session_id_val, fail_report)

        # D-026: a failed job drives the session to the 'failed' terminal state
        await _sync_session_status(session_id_val, "failed")

        return updated
