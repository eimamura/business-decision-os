from __future__ import annotations

from packages.agent.cross_domain import (
    AnomalyDetectorAgent,
    DataEngineerAgent,
    EvaluatorAgent,
    SimulationOptimizerAgent,
)

DOMAIN_AGENT_ROLES = {
    "replenishment",
    "procurement",
    "supplier",
    "production",
    "logistics",
}

CROSS_DOMAIN_AGENT_CLASSES: dict[str, type] = {
    "data_engineer": DataEngineerAgent,
    "simulation_optimizer": SimulationOptimizerAgent,
    "evaluator": EvaluatorAgent,
    "anomaly_detector": AnomalyDetectorAgent,
}

VALID_AGENT_ROLES = DOMAIN_AGENT_ROLES | set(CROSS_DOMAIN_AGENT_CLASSES)
