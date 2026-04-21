import json
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, module="mlflow")

_DB_PATH = Path("mlruns/mlflow.db")


def setup_mlflow(experiment_name: str = "fashion_intelligence") -> str:
    """
    Point MLflow at a local SQLite tracking store and return the experiment_id.

    Uses sqlite backend (filesystem store deprecated Feb 2026).
    Creates the experiment if it does not already exist.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{_DB_PATH}")
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name)
    else:
        experiment_id = experiment.experiment_id
    mlflow.set_experiment(experiment_name)
    return experiment_id


def log_segmentation_run(
    k_info: dict,
    cluster_profiles: pd.DataFrame,
    n_customers: int,
) -> str:
    """
    Log a K-Means segmentation run to MLflow.

    Cluster profiles DataFrame is saved as a CSV artifact.
    Returns the MLflow run_id.
    """
    setup_mlflow()
    with mlflow.start_run(run_name="kmeans_segmentation") as run:
        mlflow.log_params({
            "n_clusters":   k_info.get("optimal_k"),
            "n_customers":  n_customers,
        })
        mlflow.log_metrics({
            "silhouette_score": float(max(k_info.get("silhouette_scores", [0]))),
            "optimal_k":        float(k_info.get("optimal_k", 0)),
        })

        if not cluster_profiles.empty:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, prefix="cluster_profiles_"
            ) as tmp:
                cluster_profiles.to_csv(tmp.name, index=False)
                mlflow.log_artifact(tmp.name, artifact_path="cluster_profiles")

        run_id = run.info.run_id

    return run_id


def log_survival_run(
    cox_result: dict,
    km_result: dict,
    n_customers: int,
) -> str:
    """
    Log a survival analysis run (Cox PH + Kaplan-Meier) to MLflow.

    Returns the MLflow run_id.
    """
    setup_mlflow()
    with mlflow.start_run(run_name="survival_analysis") as run:
        mlflow.log_params({"n_customers": n_customers})
        mlflow.log_metrics({
            "concordance_index":   float(cox_result.get("concordance", 0)),
            "median_survival_days": float(
                km_result.get("median_survival", 0)
                if km_result.get("median_survival") not in (None, float("inf"))
                else 0
            ),
        })
        run_id = run.info.run_id

    return run_id


def log_clv_run(clv_result: dict) -> str:
    """
    Log a CLV (BG/NBD + Gamma-Gamma) run to MLflow.

    Returns the MLflow run_id.
    """
    setup_mlflow()
    with mlflow.start_run(run_name="clv_bgnbd") as run:
        mlflow.log_params({
            "n_customers": clv_result.get("n_customers", 0),
        })
        mlflow.log_metrics({
            "median_clv":          float(
                clv_result.get("clv_percentiles", {}).get("p50", 0)
            ),
            "total_predicted_clv": float(
                clv_result.get("total_predicted_clv", 0)
            ),
        })
        run_id = run.info.run_id

    return run_id


def log_tvi_run(query: str, tvi_result: dict) -> str:
    """
    Log a Trend Velocity Index scoring run to MLflow.

    Returns the MLflow run_id.
    """
    setup_mlflow()
    with mlflow.start_run(run_name=f"tvi_{query}") as run:
        mlflow.log_params({
            "query":      query,
            "confidence": tvi_result.get("confidence"),
        })
        mlflow.log_metrics({
            "tvi_score":    float(tvi_result.get("tvi", 0)),
            "google_score": float(tvi_result.get("google_score", 0)),
            "retail_score": float(tvi_result.get("retail_score", 0)),
        })
        run_id = run.info.run_id

    return run_id


if __name__ == "__main__":
    setup_mlflow()
    run_id = log_tvi_run(
        "test_query",
        {"tvi": 62.5, "confidence": "high", "google_score": 70.0, "retail_score": 55.0},
    )
    print("MLflow run logged:", run_id)
    print("MLflow tracker OK")
