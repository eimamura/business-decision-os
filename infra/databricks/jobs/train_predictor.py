"""
Databricks Job: predictor training.

Reads demand_history from PostgreSQL, computes lag and rolling features per SKU,
trains a scikit-learn LinearRegression model per SKU, and logs everything to the
MLflow experiment /bdos/predictor-training.  Registers the final model in the
MLflow Model Registry as 'bdos-demand-predictor'.

Usage:
    python train_predictor.py \
        --jdbc-url "postgresql://user:pass@host:5432/db" \
        --mlflow-tracking-uri "databricks" \
        --experiment-name "/bdos/predictor-training"
"""

import argparse
import os
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train demand predictor per SKU")
    parser.add_argument(
        "--jdbc-url",
        default=os.environ.get("JDBC_URL"),
        help="PostgreSQL JDBC URL (jdbc:postgresql://... or postgresql://...)",
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "databricks"),
        help="MLflow tracking URI (default: 'databricks' for Databricks-managed tracking)",
    )
    parser.add_argument(
        "--experiment-name",
        default=os.environ.get("MLFLOW_EXPERIMENT_NAME", "/bdos/predictor-training"),
        help="MLflow experiment name",
    )
    return parser.parse_args()


def load_demand_history(jdbc_url: str) -> pd.DataFrame:
    """Load demand_history from PostgreSQL via pandas + psycopg2."""
    query = """
        SELECT sku, date, units
        FROM demand_history
        WHERE units IS NOT NULL
        ORDER BY sku, date
    """
    return pd.read_sql(query, con=jdbc_url)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute lag and rolling features per SKU.

    Features produced:
      - lag_7d:          demand 7 days prior
      - lag_28d:         demand 28 days prior
      - rolling_mean_7d: 7-day rolling mean (exclusive of current row)
      - rolling_std_7d:  7-day rolling standard deviation (exclusive of current row)
    """
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


def train_sku_model(
    sku_id: str, sku_df: pd.DataFrame
) -> tuple[LinearRegression, dict[str, Any]]:
    """Train a LinearRegression model for a single SKU and return metrics."""
    feature_cols = ["lag_7d", "lag_28d", "rolling_mean_7d", "rolling_std_7d"]
    target_col = "units"

    clean = sku_df.dropna(subset=feature_cols + [target_col])
    if len(clean) < 10:
        raise ValueError(f"SKU {sku_id}: insufficient clean rows ({len(clean)})")

    X = clean[feature_cols].values
    y = clean[target_col].values

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)
    metrics = {
        "mae": float(mean_absolute_error(y, y_pred)),
        "rmse": float(mean_squared_error(y, y_pred) ** 0.5),
        "n_samples": int(len(clean)),
    }
    return model, metrics


def run(jdbc_url: str, mlflow_tracking_uri: str, experiment_name: str) -> None:
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    raw_df = load_demand_history(jdbc_url)
    features_df = compute_features(raw_df)

    sku_ids = features_df["sku_id"].unique().tolist()
    best_run_id: str | None = None

    for sku_id in sku_ids:
        sku_df = features_df[features_df["sku_id"] == sku_id]
        try:
            model, metrics = train_sku_model(sku_id, sku_df)
        except ValueError as exc:
            print(f"[WARN] Skipping {sku_id}: {exc}")
            continue

        with mlflow.start_run(run_name=f"train_{sku_id}") as run:
            mlflow.log_param("sku_id", sku_id)
            mlflow.log_param("model_type", "linear_regression")
            mlflow.log_params(
                {
                    "features": "lag_7d,lag_28d,rolling_mean_7d,rolling_std_7d",
                    "n_samples": metrics["n_samples"],
                }
            )
            mlflow.log_metrics({"mae": metrics["mae"], "rmse": metrics["rmse"]})
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="model",
                registered_model_name="bdos-demand-predictor",
                input_example=None,
            )
            best_run_id = run.info.run_id
            print(
                f"[INFO] SKU {sku_id} — MAE={metrics['mae']:.4f}  RMSE={metrics['rmse']:.4f}  run_id={run.info.run_id}"
            )

    if best_run_id is None:
        raise RuntimeError("No SKU models were successfully trained.")

    print(f"[INFO] Training complete. Last registered run_id: {best_run_id}")


if __name__ == "__main__":
    args = parse_args()

    if not args.jdbc_url:
        raise RuntimeError(
            "JDBC_URL environment variable or --jdbc-url argument is required."
        )

    run(
        jdbc_url=args.jdbc_url,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        experiment_name=args.experiment_name,
    )
