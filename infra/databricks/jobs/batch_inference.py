"""
Databricks Job: batch inference.

Loads the latest 'bdos-demand-predictor' model version from the MLflow Model
Registry, reads recent demand_history from PostgreSQL, computes prediction
features per SKU (same pipeline as training), runs 28-day horizon predictions,
and writes results back to the PostgreSQL 'prediction_features' table via an
upsert (ON CONFLICT DO UPDATE).

Table contract for prediction_features:
    sku_id           TEXT          PRIMARY KEY
    horizon_days     INTEGER
    predicted_units  FLOAT[]
    model_version    TEXT          e.g. "linear_regression_v<run_id[:8]>"
    computed_at      TIMESTAMPTZ

Usage:
    python batch_inference.py \
        --jdbc-url "postgresql://user:pass@host:5432/db" \
        --mlflow-tracking-uri "databricks"
"""

import argparse
import os
from datetime import datetime, timezone

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras


REGISTERED_MODEL_NAME = "bdos-demand-predictor"
HORIZON_DAYS = 28
FEATURE_COLS = ["lag_7d", "lag_28d", "rolling_mean_7d", "rolling_std_7d"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch demand prediction per SKU")
    parser.add_argument(
        "--jdbc-url",
        default=os.environ.get("JDBC_URL"),
        help="PostgreSQL connection URL (postgresql://user:pass@host:5432/db)",
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "databricks"),
        help="MLflow tracking URI (default: 'databricks')",
    )
    return parser.parse_args()


def load_latest_model(
    mlflow_tracking_uri: str,
) -> tuple[object, str]:
    """Return (model, model_version_string) for the latest Production model."""
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    client = mlflow.tracking.MlflowClient()

    versions = client.get_latest_versions(
        REGISTERED_MODEL_NAME, stages=["Production", "None"]
    )
    if not versions:
        raise RuntimeError(
            f"No versions found for registered model '{REGISTERED_MODEL_NAME}'."
        )

    latest = sorted(versions, key=lambda v: int(v.version), reverse=True)[0]
    run_id = latest.run_id
    model_uri = f"runs:/{run_id}/model"
    model = mlflow.sklearn.load_model(model_uri)
    model_version = f"linear_regression_v{run_id[:8]}"
    print(f"[INFO] Loaded model version={latest.version} run_id={run_id}")
    return model, model_version


def load_demand_history(jdbc_url: str) -> pd.DataFrame:
    """Load the most recent demand_history rows needed to compute features."""
    query = """
        SELECT sku, date, units
        FROM demand_history
        WHERE units IS NOT NULL
        ORDER BY sku, date
    """
    return pd.read_sql(query, con=jdbc_url)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute lag and rolling features per SKU (same pipeline as training)."""
    results: list[pd.DataFrame] = []
    for sku_id, group in df.groupby("sku"):
        g = group.sort_values("date").copy()
        g["lag_7d"] = g["units"].shift(7)
        g["lag_28d"] = g["units"].shift(28)
        g["rolling_mean_7d"] = g["units"].shift(1).rolling(window=7).mean()
        g["rolling_std_7d"] = g["units"].shift(1).rolling(window=7).std()
        g["sku_id"] = sku_id
        results.append(g)
    return pd.concat(results, ignore_index=True)


def predict_sku(
    model: object, sku_df: pd.DataFrame
) -> list[float]:
    """
    Generate HORIZON_DAYS predictions for a single SKU using the last known
    feature vector and an auto-regressive rollout.
    """
    clean = sku_df.dropna(subset=FEATURE_COLS).sort_values("date")
    if clean.empty:
        return [0.0] * HORIZON_DAYS

    last_row = clean.iloc[-1][FEATURE_COLS].values.astype(float)
    predictions: list[float] = []

    for _ in range(HORIZON_DAYS):
        pred = float(model.predict([last_row])[0])
        pred = max(0.0, pred)
        predictions.append(pred)
        # Shift features forward: new lag_7d becomes the previous lag_7d,
        # new lag_28d stays (approximation for multi-step rollout).
        last_row = np.array(
            [
                pred,                # lag_7d  ← latest prediction
                last_row[0],         # lag_28d ← previous lag_7d
                (last_row[2] * 6 + pred) / 7,   # rolling_mean_7d updated
                last_row[3],         # rolling_std_7d unchanged (approximation)
            ]
        )

    return predictions


def upsert_predictions(
    jdbc_url: str,
    rows: list[dict],
) -> None:
    """Write prediction rows to prediction_features using ON CONFLICT upsert."""
    upsert_sql = """
        INSERT INTO prediction_features
            (sku_id, horizon_days, predicted_units, model_version, computed_at)
        VALUES
            (%(sku_id)s, %(horizon_days)s, %(predicted_units)s,
             %(model_version)s, %(computed_at)s)
        ON CONFLICT (sku_id) DO UPDATE SET
            horizon_days    = EXCLUDED.horizon_days,
            predicted_units = EXCLUDED.predicted_units,
            model_version   = EXCLUDED.model_version,
            computed_at     = EXCLUDED.computed_at
    """
    with psycopg2.connect(jdbc_url) as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, upsert_sql, rows)
        conn.commit()
    print(f"[INFO] Upserted {len(rows)} prediction rows.")


def run(jdbc_url: str, mlflow_tracking_uri: str) -> None:
    model, model_version = load_latest_model(mlflow_tracking_uri)

    raw_df = load_demand_history(jdbc_url)
    features_df = compute_features(raw_df)

    computed_at = datetime.now(timezone.utc)
    rows: list[dict] = []

    for sku_id, sku_df in features_df.groupby("sku_id"):
        predictions = predict_sku(model, sku_df)
        rows.append(
            {
                "sku_id": str(sku_id),
                "horizon_days": HORIZON_DAYS,
                "predicted_units": predictions,
                "model_version": model_version,
                "computed_at": computed_at,
            }
        )
        print(
            f"[INFO] SKU {sku_id} — {HORIZON_DAYS}-day forecast computed. "
            f"day1={predictions[0]:.2f}  day28={predictions[-1]:.2f}"
        )

    if not rows:
        raise RuntimeError("No prediction rows generated — check demand_history data.")

    upsert_predictions(jdbc_url, rows)
    print("[INFO] Batch inference complete.")


if __name__ == "__main__":
    args = parse_args()

    if not args.jdbc_url:
        raise RuntimeError(
            "JDBC_URL environment variable or --jdbc-url argument is required."
        )

    run(
        jdbc_url=args.jdbc_url,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
    )
