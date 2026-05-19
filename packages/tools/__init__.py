from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.forecast_tool import ForecastTool
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
    "OptimizerTool",
    "SimulationTool",
    "SqlQueryTool",
    "create_tool_registry",
]


def create_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SqlQueryTool())
    registry.register(ApprovalTool())
    registry.register(AuditLogTool())
    registry.register(ForecastTool())
    registry.register(SimulationTool())
    registry.register(OptimizerTool())
    registry.register(EvaluatorTool())
    return registry
