from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class PredictorResult:
    sku_id: str
    predicted_units: list[float]
    model_version: str
    source: str


@runtime_checkable
class Predictor(Protocol):
    async def predict(self, sku_id: str, horizon_days: int) -> PredictorResult: ...


class DatabasePredictor:
    def __init__(self, db_session: Any) -> None:
        self._db_session = db_session
        self._fallback = LinearRegressionPredictor(db_session)

    async def predict(self, sku_id: str, horizon_days: int) -> PredictorResult:
        from sqlalchemy import text

        sql = text(
            "SELECT predicted_units, model_version FROM prediction_features "
            "WHERE sku_id = :sku_id LIMIT 1"
        )
        result = await self._db_session.execute(sql, {"sku_id": sku_id})
        row = result.fetchone()

        if row is None:
            fallback = await self._fallback.predict(sku_id, horizon_days)
            return PredictorResult(
                sku_id=sku_id,
                predicted_units=fallback.predicted_units,
                model_version=fallback.model_version,
                source="databricks_features",
            )

        raw_units = row[0]
        model_version: str = row[1]

        if isinstance(raw_units, list):
            predicted_units = [float(v) for v in raw_units[:horizon_days]]
            if len(predicted_units) < horizon_days:
                mean_val = sum(predicted_units) / len(predicted_units) if predicted_units else 0.0
                predicted_units += [mean_val] * (horizon_days - len(predicted_units))
        else:
            predicted_units = [float(raw_units)] * horizon_days

        return PredictorResult(
            sku_id=sku_id,
            predicted_units=predicted_units,
            model_version=model_version,
            source="databricks_features",
        )


class LinearRegressionPredictor:
    def __init__(self, db_session: Any | None = None) -> None:
        self._db_session = db_session

    async def predict(self, sku_id: str, horizon_days: int) -> PredictorResult:
        history = await self._fetch_history(sku_id)

        if len(history) < 3:
            mean_val = sum(history) / len(history) if history else 0.0
            return PredictorResult(
                sku_id=sku_id,
                predicted_units=[mean_val] * horizon_days,
                model_version="linear_regression_v1_fallback",
                source="in_process",
            )

        predicted = self._fit_and_predict(history, horizon_days)
        return PredictorResult(
            sku_id=sku_id,
            predicted_units=predicted,
            model_version="linear_regression_v1",
            source="in_process",
        )

    async def _fetch_history(self, sku_id: str) -> list[float]:
        if self._db_session is None:
            return []

        from sqlalchemy import text

        sql = text(
            "SELECT units FROM demand_history "
            "WHERE sku = :sku AND units IS NOT NULL "
            "ORDER BY date DESC LIMIT 90"
        )
        result = await self._db_session.execute(sql, {"sku": sku_id})
        rows = result.fetchall()
        return [float(row[0]) for row in rows]

    def _fit_and_predict(self, history: list[float], horizon_days: int) -> list[float]:
        import numpy as np
        from sklearn.linear_model import LinearRegression

        n = len(history)
        x = np.arange(n).reshape(-1, 1)
        y = np.array(history)

        model = LinearRegression()
        model.fit(x, y)

        future_x = np.arange(n, n + horizon_days).reshape(-1, 1)
        predictions = model.predict(future_x)
        return [float(v) for v in predictions]
