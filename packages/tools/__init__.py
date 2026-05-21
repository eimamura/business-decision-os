from __future__ import annotations

from typing import Any

from packages.prediction import LinearRegressionPredictor
from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.forecast_tool import ForecastTool
from packages.tools.nl_query_tool import NlQueryTool
from packages.tools.optimizer_tool import OptimizerTool
from packages.tools.simulation_tool import SimulationTool
from packages.tools.sql_tool import SqlQueryTool

__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ApprovalTool",
    "AuditLogTool",
    "EvaluatorTool",
    "ForecastTool",
    "NlQueryTool",
    "OptimizerTool",
    "SimulationTool",
    "SqlQueryTool",
    "create_tool_registry",
]


def create_tool_registry(job_runner: Any = None, db_session: Any = None) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SqlQueryTool(db_session=db_session))
    registry.register(NlQueryTool())
    registry.register(ApprovalTool())
    registry.register(AuditLogTool())
    registry.register(ForecastTool(predictor=LinearRegressionPredictor(db_session=db_session)))
    registry.register(SimulationTool(job_runner=job_runner))
    registry.register(OptimizerTool())
    registry.register(EvaluatorTool())
    return registry
