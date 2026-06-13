"""T-416 (updated in P101-T-600): Registry presence tests for gap-5 tools.

write_audit_log and train_forecast remain non-LLM-callable.
job_dispatch was re-registered as LLM-callable in P101-T-600 (safety_level="hitl");
the old "not in registry" assertion is replaced by a "present with hitl" assertion.
"""
from __future__ import annotations

from packages.tools import AuditLogTool, JobDispatchTool, TrainForecastTool, create_tool_registry


def test_write_audit_log_not_in_registry() -> None:
    """write_audit_log must not be registered as an LLM-callable tool."""
    registry = create_tool_registry()
    assert "write_audit_log" not in registry._tools, (
        "write_audit_log must not be LLM-callable (removed by P64 T-408)"
    )


def test_job_dispatch_in_registry_with_hitl_safety_level() -> None:
    """job_dispatch must be LLM-callable with safety_level='hitl' (P101-T-600).

    P64 removed it; P81 deferred re-registration; P101-T-600 re-registers it.
    The HITL gate in AgentRuntime.prepare_hitl intercepts before handle() is called.
    """
    registry = create_tool_registry()
    assert "job_dispatch" in registry._tools, (
        "job_dispatch must be re-registered as LLM-callable (P101-T-600)"
    )
    tool = registry._tools["job_dispatch"]
    assert tool.safety_level == "hitl", (
        f"job_dispatch safety_level must be 'hitl', got {tool.safety_level!r}"
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
