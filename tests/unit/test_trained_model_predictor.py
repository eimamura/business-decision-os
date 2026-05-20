from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.prediction import Predictor, TrainedModelPredictor


def _make_db_session_with_row(predicted_units: list[float], model_version: str) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda i: predicted_units if i == 0 else model_version)
    execute_result = MagicMock()
    execute_result.fetchone.return_value = row
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _make_db_session_no_row() -> MagicMock:
    execute_result = MagicMock()
    execute_result.fetchone.return_value = None
    execute_result.fetchall.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    return session


def test_trained_model_predictor_satisfies_protocol():
    session = MagicMock()
    predictor = TrainedModelPredictor(session)
    assert isinstance(predictor, Predictor)


@pytest.mark.asyncio
async def test_trained_model_predictor_returns_stored_units():
    stored_units = [float(i) for i in range(90)]
    session = _make_db_session_with_row(stored_units, "linear_regression_v1_trained")

    predictor = TrainedModelPredictor(session)
    result = await predictor.predict("SKU-1", 10)

    assert result.source == "trained_model"
    assert result.sku_id == "SKU-1"
    assert result.predicted_units == stored_units[:10]
    assert result.model_version == "linear_regression_v1_trained"


@pytest.mark.asyncio
async def test_trained_model_predictor_fallback_when_no_row():
    session = _make_db_session_no_row()

    predictor = TrainedModelPredictor(session)
    result = await predictor.predict("SKU-MISSING", 10)

    assert result.source == "in_process_fallback"
    assert result.sku_id == "SKU-MISSING"
    assert len(result.predicted_units) == 10
