from __future__ import annotations

from typing import Any

from packages.agent.llm import LLMClient
from packages.prediction import DatabasePredictor
from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from packages.tools.data_catalog_search_tool import DataCatalogSearchTool
from packages.tools.data_quality_checker_tool import DataQualityCheckerTool
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.forecast_tool import ForecastTool
from packages.tools.job_dispatch_tool import JobDispatchTool
from packages.tools.nl_query_tool import NlQueryTool
from packages.tools.optimizer_tool import OptimizerTool
from packages.tools.simulation_tool import SimulationTool
from packages.tools.sql_tool import SqlQueryTool
from packages.tools.table_schema_reader_tool import TableSchemaReaderTool
from packages.tools.train_forecast_tool import TrainForecastTool

__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ApprovalTool",
    "AuditLogTool",
    "DataCatalogSearchTool",
    "DataQualityCheckerTool",
    "EvaluatorTool",
    "ForecastTool",
    "JobDispatchTool",
    "NlQueryTool",
    "OptimizerTool",
    "SimulationTool",
    "SqlQueryTool",
    "TableSchemaReaderTool",
    "TrainForecastTool",
    "create_tool_registry",
]


def create_tool_registry(
    runner: Any = None,
    db_session: Any = None,
    llm_client: LLMClient | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SqlQueryTool(db_session=db_session))
    registry.register(NlQueryTool(llm_client=llm_client))
    registry.register(ApprovalTool())
    registry.register(AuditLogTool())
    registry.register(ForecastTool(predictor=DatabasePredictor(db_session=db_session)))
    registry.register(SimulationTool(runner=runner))
    registry.register(TrainForecastTool(runner=runner))
    registry.register(OptimizerTool())
    registry.register(EvaluatorTool())
    registry.register(DataCatalogSearchTool())
    registry.register(TableSchemaReaderTool())
    registry.register(DataQualityCheckerTool())
    registry.register(JobDispatchTool())
    return registry
