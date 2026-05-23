from __future__ import annotations

from packages.persistence.db import get_pool


async def fetch_demand_history(sku_id: str) -> list[float]:
    try:
        pool = await get_pool()
    except RuntimeError:
        return []
    async with pool.acquire() as conn:
        sql = (
            "SELECT quantity FROM demand_history WHERE sku_id = $1 "
            "AND quantity IS NOT NULL ORDER BY date DESC LIMIT 90"
        )
        rows = await conn.fetch(sql, sku_id)
        return [float(row["quantity"]) for row in rows]


async def upsert_prediction(sku_id: str, predicted_units: list[float], model_version: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO prediction_features (sku_id, predicted_units, model_version) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (sku_id) DO UPDATE SET "
            "predicted_units = EXCLUDED.predicted_units, model_version = EXCLUDED.model_version",
            sku_id, predicted_units, model_version,
        )
