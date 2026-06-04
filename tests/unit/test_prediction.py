from __future__ import annotations

from uuid import uuid4

import pytest

from packages.prediction import LinearRegressionPredictor, Predictor, PredictorResult
from packages.tools.base import ToolContext
from packages.tools.forecast_tool import ForecastTool


def _make_tool_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


async def test_linear_regression_predictor_no_db_returns_fallback():
    predictor = LinearRegressionPredictor(db_session=None)
    result = await predictor.predict("SKU001", 7)

    assert isinstance(result, PredictorResult)
    assert result.sku_id == "SKU001"
    assert result.model_version == "linear_regression_v1_fallback"
    assert len(result.predicted_units) == 7
    assert result.source == "in_process"


async def test_linear_regression_predictor_fallback_all_zeros():
    predictor = LinearRegressionPredictor(db_session=None)
    result = await predictor.predict("SKU_UNKNOWN", 14)

    assert result.predicted_units == [0.0] * 14


def test_predictor_result_has_expected_fields():
    r = PredictorResult(
        sku_id="SKU-TEST",
        predicted_units=[5.0, 6.0, 7.0],
        model_version="linear_regression_v1",
        source="in_process",
    )
    assert r.sku_id == "SKU-TEST"
    assert r.predicted_units == [5.0, 6.0, 7.0]
    assert r.model_version == "linear_regression_v1"
    assert r.source == "in_process"


def test_predictor_protocol_is_satisfied():
    predictor = LinearRegressionPredictor(db_session=None)
    assert isinstance(predictor, Predictor)


def test_forecast_tool_raises_without_predictor():
    with pytest.raises(RuntimeError, match="requires a predictor"):
        ForecastTool(predictor=None)


async def test_forecast_tool_with_predictor_returns_output():
    predictor = LinearRegressionPredictor(db_session=None)
    tool = ForecastTool(predictor=predictor)
    ctx = _make_tool_ctx()
    tool_result = await tool.handle({"sku_id": "SKU001", "horizon_days": 10}, ctx)

    output = tool_result.output
    assert output["sku_id"] == "SKU001"
    assert len(output["forecast_units"]) == 10
    assert output["model_version"] == "linear_regression_v1_fallback"
    assert output["source"] == "in_process"
    assert output["prediction"] == output["forecast_units"][0]
