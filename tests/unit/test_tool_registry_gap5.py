"""T-416: Assert that write_audit_log, job_dispatch, and train_forecast are NOT
in create_tool_registry() (Gap 5 — P64 B-02, T-408).

Also asserts that the three tool classes can still be instantiated directly,
confirming the class files remain intact even though the tools are no longer
LLM-callable.
"""
from __future__ import annotations

import pytest

from packages.tools import AuditLogTool, JobDispatchTool, TrainForecastTool, create_tool_registry


def test_write_audit_log_not_in_registry() -> None:
    """write_audit_log must not be registered as an LLM-callable tool."""
    registry = create_tool_registry()
    assert "write_audit_log" not in registry._tools, (
        "write_audit_log must not be LLM-callable (removed by P64 T-408)"
    )


def test_job_dispatch_not_in_registry() -> None:
    """job_dispatch must not be registered as an LLM-callable tool."""
    registry = create_tool_registry()
    assert "job_dispatch" not in registry._tools, (
        "job_dispatch must not be LLM-callable (removed by P64 T-408)"
    )


def test_train_forecast_not_in_registry() -> None:
    """train_forecast must not be registered as an LLM-callable tool."""
    registry = create_tool_registry()
    assert "train_forecast" not in registry._tools, (
        "train_forecast must not be LLM-callable (removed by P64 T-408)"
    )


def test_audit_log_tool_class_is_still_instantiable() -> None:
    """AuditLogTool class must still be importable and instantiable."""
    tool = AuditLogTool()
    assert tool is not None
    assert hasattr(tool, "handle")


def test_job_dispatch_tool_class_is_still_instantiable() -> None:
    """JobDispatchTool class must still be importable and instantiable."""
    tool = JobDispatchTool()
    assert tool is not None
    assert hasattr(tool, "handle")


def test_train_forecast_tool_class_is_still_instantiable() -> None:
    """TrainForecastTool class must still be importable and instantiable."""
    tool = TrainForecastTool()
    assert tool is not None
    assert hasattr(tool, "handle")
