"""
Fashion Intelligence — Customer Analysis Pipeline
Run once (or periodically) to process H&M data and populate DuckDB.

Usage:
    python run_customer_analysis.py
    python run_customer_analysis.py --sample 10000
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import pandas as pd

# Ensure UTF-8 output so emoji print correctly on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from data_sources.hm_loader import (
    check_hm_data_available,
    get_data_summary,
    load_sample,
)
from analytics.rfm import build_rfm_pipeline
from analytics.segmentation import run_segmentation
from analytics.churn_labeller import (
    compute_churn_stats,
    determine_churn_threshold,
    label_churn,
)
from analytics.survival_analysis import run_survival_analysis
from analytics.clv import run_clv_analysis
from analytics.recommender import run_recommender_pipeline
from database.db_manager import DatabaseManager
from observability.mlflow_tracker import (
    log_clv_run,
    log_segmentation_run,
    log_survival_run,
    setup_mlflow,
)
from observability.data_validators import validate_rfm_input

# ── Schema column order for customer_segments (must match schema.sql) ─────────
_CS_COLS = [
    "customer_id", "recency_days", "frequency", "monetary",
    "rfm_score", "cluster_id", "cluster_label",
    "churn_probability", "clv_12m", "segmented_at",
]


def run_analysis(sample_customers: int = 50_000):
    print("=" * 60)
    print("🧠 Fashion Intelligence — Customer Analysis Pipeline")
    print("=" * 60)

    # ── Step 1: Check data ────────────────────────────────────────────────────
    if not check_hm_data_available():
        print("❌ H&M data not found in data/hm/")
        print("   Download from: https://www.kaggle.com/competitions/"
              "h-and-m-personalized-fashion-recommendations/data")
        print("   Place files: articles.csv, customers.csv, "
              "transactions_train.csv in data/hm/")
        return

    print(f"✅ H&M data found: {get_data_summary()}")

    # ── Step 2: Load sample ───────────────────────────────────────────────────
    print(f"\n📥 Loading {sample_customers:,} customer sample...")
    data         = load_sample(n_customers=sample_customers)
    transactions = data["transactions"]
    articles     = data["articles"]
    customers    = data["customers"]
    print(f"   Transactions: {len(transactions):,} | "
          f"Customers: {len(customers):,} | "
          f"Articles: {len(articles):,}")

    # ── Step 3: Validate ──────────────────────────────────────────────────────
    is_valid, n_errors = validate_rfm_input(transactions)
    print(f"   Data validation: "
          f"{'✅ OK' if is_valid else f'⚠️ {n_errors} issues (continuing anyway)'}")

    # ── Step 4: RFM ───────────────────────────────────────────────────────────
    print("\n🧮 Computing RFM features...")
    rfm_df = build_rfm_pipeline(transactions)
    print(f"   RFM complete: {len(rfm_df)} customers | "
          f"Segments: {rfm_df['segment'].value_counts().to_dict()}")

    # ── Step 5: Segmentation ──────────────────────────────────────────────────
    print("\n🎯 Running K-Means segmentation...")
    seg_result = run_segmentation(rfm_df)
    print(f"   Optimal K: {seg_result['n_clusters']} | "
          f"Cluster names: {seg_result['cluster_names']}")

    # ── Step 6: Churn ─────────────────────────────────────────────────────────
    print("\n📉 Labelling churn...")
    threshold   = determine_churn_threshold(transactions)
    print(f"   Churn threshold: {threshold['threshold_days']:.0f} days "
          f"(p{threshold['percentile_used']:.0f})")
    churn_df    = label_churn(transactions)
    churn_stats = compute_churn_stats(churn_df)
    print(f"   Churn rate: {churn_stats['churn_rate']:.1%} | "
          f"Active: {churn_stats['active']:,} | "
          f"Churned: {churn_stats['churned']:,}")

    # ── Step 7: Survival analysis ─────────────────────────────────────────────
    print("\n📊 Running survival analysis...")
    survival_result = run_survival_analysis(transactions, customers)
    survival_ok = survival_result.get("available", True)   # absent key → success
    if survival_ok:
        med = survival_result["km_overall"]["median_survival"]
        med_str = f"{med:.0f}" if med != float("inf") else "∞"
        print(f"   Median survival: {med_str} days")
        print(f"   Cox concordance: {survival_result['cox']['concordance']:.3f}")
    else:
        print("   ⚠️ Survival analysis skipped (insufficient data)")

    # ── Step 8: CLV ───────────────────────────────────────────────────────────
    print("\n💰 Computing Customer Lifetime Value...")
    clv_result = run_clv_analysis(transactions)
    if clv_result["available"]:
        print(f"   Median 12m CLV: ${clv_result['clv_percentiles']['p50']:.2f}")
        print(f"   Total projected: ${clv_result['total_predicted_clv']:,.0f}")
    else:
        print(f"   ⚠️ CLV skipped: {clv_result.get('reason', 'unknown')}")

    # ── Step 9: Recommender ───────────────────────────────────────────────────
    print("\n🎲 Training recommendation model...")
    rec_result = run_recommender_pipeline(transactions, articles)
    print(f"   Recommender: "
          f"{'✅ trained' if rec_result['available'] else '⚠️ insufficient data'}")

    # ── Step 10: Save to DuckDB ───────────────────────────────────────────────
    print("\n💾 Saving to DuckDB...")
    try:
        _save_customer_segments(seg_result, churn_df, clv_result)
    except Exception as exc:
        print(f"   ⚠️ DuckDB save failed: {exc}")

    # ── Step 11: Log to MLflow ────────────────────────────────────────────────
    print("\n📝 Logging experiments to MLflow...")
    try:
        setup_mlflow()
        log_segmentation_run(
            seg_result["k_info"],
            seg_result["cluster_profiles"],
            len(rfm_df),
        )
        if survival_ok:
            log_survival_run(
                survival_result["cox"],
                survival_result["km_overall"],
                survival_result["n_customers"],
            )
        if clv_result["available"]:
            log_clv_run(clv_result)
        print("   ✅ Experiments logged (run: mlflow ui)")
    except Exception as exc:
        print(f"   ⚠️ MLflow logging failed: {exc}")

    print("\n" + "=" * 60)
    print("✅ Customer Intelligence Pipeline Complete!")
    print("   View results: streamlit run app.py")
    print("   View MLflow:  mlflow ui")
    print("=" * 60)


def _save_customer_segments(
    seg_result: dict,
    churn_df: pd.DataFrame,
    clv_result: dict,
) -> None:
    """
    Build the customer_segments DataFrame in schema column order and upsert to DuckDB.
    """
    segments_df = seg_result["rfm_with_clusters"].copy()

    # Churn probability lookup (1.0 = churned, 0.0 = active)
    churn_lookup = churn_df.set_index("customer_id")["churned"].astype(float)

    # CLV lookup
    clv_lookup = None
    if clv_result.get("available") and "clv_df" in clv_result:
        clv_lookup = clv_result["clv_df"]["clv"]

    save_df = pd.DataFrame()
    save_df["customer_id"]       = segments_df["customer_id"]
    save_df["recency_days"]      = segments_df["recency"].astype(int)
    save_df["frequency"]         = segments_df["frequency"].astype(int)
    save_df["monetary"]          = segments_df["monetary"].astype(float)
    save_df["rfm_score"]         = (
        segments_df["rfm_string"]
        if "rfm_string" in segments_df.columns
        else "000"
    )
    save_df["cluster_id"]        = segments_df["cluster_id"].astype(int)
    save_df["cluster_label"]     = segments_df.get("cluster_name",
                                     segments_df.get("segment", "Unknown"))
    save_df["churn_probability"] = (
        save_df["customer_id"].map(churn_lookup).fillna(0.0)
    )
    save_df["clv_12m"]           = (
        save_df["customer_id"].map(clv_lookup).fillna(0.0)
        if clv_lookup is not None else 0.0
    )
    save_df["segmented_at"]      = datetime.datetime.now(datetime.timezone.utc)

    # Enforce schema column order
    save_df = save_df[_CS_COLS]

    with DatabaseManager() as db:
        db.conn.execute("DELETE FROM customer_segments")
        db.conn.execute("INSERT INTO customer_segments SELECT * FROM save_df")
        print(f"   ✅ Saved {len(save_df):,} customer segments to DuckDB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Fashion Intelligence customer analysis pipeline."
    )
    parser.add_argument(
        "--sample", type=int, default=50_000,
        help="Number of customers to sample (default: 50000)",
    )
    args = parser.parse_args()
    run_analysis(sample_customers=args.sample)
