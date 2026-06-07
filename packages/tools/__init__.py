from __future__ import annotations

from typing import Any

from packages.prediction import DatabasePredictor
from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from packages.tools.data_catalog_search_tool import DataCatalogSearchTool
from packages.tools.data_quality_checker_tool import DataQualityCheckerTool
from packages.tools.demand_anomaly_tool import DemandAnomalyTool
from packages.tools.demand_compare_tool import DemandCompareTool
from packages.tools.demand_drivers_tool import DemandDriversTool
from packages.tools.demand_profile_tool import DemandProfileTool
from packages.tools.demand_seasonality_tool import DemandSeasonalityTool
from packages.tools.demand_segment_tool import DemandSegmentTool
from packages.tools.demand_trend_tool import DemandTrendTool
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.finance_expedite_cost_tool import CalculateExpediteCostTool
from packages.tools.finance_holding_cost_tool import CalculateHoldingCostImpactTool
from packages.tools.finance_scenario_tool import CompareCostScenariosTool
from packages.tools.finance_stockout_cost_tool import CalculateStockoutCostImpactTool
from packages.tools.forecast_accuracy_tool import ForecastAccuracyTool
from packages.tools.forecast_tool import ForecastTool
from packages.tools.inventory_atp_tool import GetAvailableToPromiseTool
from packages.tools.inventory_doi_tool import CalculateDaysOfInventoryTool
from packages.tools.inventory_excess_tool import CalculateExcessInventoryRiskTool
from packages.tools.inventory_stockout_risk_tool import CalculateStockoutRiskTool
from packages.tools.job_dispatch_tool import JobDispatchTool
from packages.tools.nl_query_tool import NlQueryTool
from packages.tools.optimizer_tool import OptimizerTool
from packages.tools.simulation_tool import SimulationTool
from packages.tools.supply_days_tool import CalculateDaysOfSupplyTool
from packages.tools.supply_delayed_orders_tool import GetDelayedSupplyOrdersTool
from packages.tools.supply_gap_tool import CalculateSupplyGapTool
from packages.tools.supply_lead_time_tool import AnalyzeSupplyLeadTimeTool
from packages.tools.supply_open_orders_tool import GetOpenSupplyOrdersTool
from packages.tools.supply_risk_tool import AnalyzeSupplyRiskTool
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
    "DemandAnomalyTool",
    "DemandCompareTool",
    "DemandDriversTool",
    "DemandProfileTool",
    "DemandSegmentTool",
    "DemandSeasonalityTool",
    "DemandTrendTool",
    "EvaluatorTool",
    "CalculateExpediteCostTool",
    "CalculateHoldingCostImpactTool",
    "CompareCostScenariosTool",
    "CalculateStockoutCostImpactTool",
    "ForecastAccuracyTool",
    "ForecastTool",
    "JobDispatchTool",
    "NlQueryTool",
    "OptimizerTool",
    "SimulationTool",
    "CalculateDaysOfSupplyTool",
    "CalculateSupplyGapTool",
    "AnalyzeSupplyLeadTimeTool",
    "GetDelayedSupplyOrdersTool",
    "GetOpenSupplyOrdersTool",
    "AnalyzeSupplyRiskTool",
    "GetAvailableToPromiseTool",
    "CalculateDaysOfInventoryTool",
    "CalculateExcessInventoryRiskTool",
    "CalculateStockoutRiskTool",
    "TableSchemaReaderTool",
    "TrainForecastTool",
    "create_tool_registry",
]


def create_tool_registry(
    runner: Any = None,
    db_session: Any = None,
    model: Any = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(NlQueryTool(model=model))
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
    registry.register(DemandProfileTool(db_session=db_session))
    registry.register(DemandTrendTool(db_session=db_session))
    registry.register(ForecastAccuracyTool(db_session=db_session))
    registry.register(DemandAnomalyTool(db_session=db_session))
    registry.register(DemandSeasonalityTool(db_session=db_session))
    registry.register(DemandDriversTool(db_session=db_session))
    registry.register(DemandSegmentTool(db_session=db_session))
    registry.register(DemandCompareTool(db_session=db_session))
    registry.register(GetOpenSupplyOrdersTool(db_session=db_session))
    registry.register(GetDelayedSupplyOrdersTool(db_session=db_session))
    registry.register(CalculateSupplyGapTool(db_session=db_session))
    registry.register(AnalyzeSupplyLeadTimeTool(db_session=db_session))
    registry.register(CalculateDaysOfSupplyTool(db_session=db_session))
    registry.register(AnalyzeSupplyRiskTool(db_session=db_session))
    registry.register(CalculateHoldingCostImpactTool(db_session=db_session))
    registry.register(CalculateStockoutCostImpactTool(db_session=db_session))
    registry.register(CalculateExpediteCostTool(db_session=db_session))
    registry.register(CompareCostScenariosTool(db_session=db_session))
    registry.register(CalculateDaysOfInventoryTool(db_session=db_session))
    registry.register(CalculateStockoutRiskTool(db_session=db_session))
    registry.register(CalculateExcessInventoryRiskTool(db_session=db_session))
    registry.register(GetAvailableToPromiseTool(db_session=db_session))
    return registry
