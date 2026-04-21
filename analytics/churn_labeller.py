import numpy as np
import pandas as pd
from datetime import timedelta
from scipy import stats


def compute_purchase_gaps(transactions_df: pd.DataFrame) -> pd.Series:
    """
    Compute days between consecutive purchases for every customer.

    Returns a flat Series of all inter-purchase gap values (in days).
    """
    df = transactions_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df.sort_values(["customer_id", "transaction_date"])

    gaps = (
        df.groupby("customer_id")["transaction_date"]
        .apply(lambda dates: dates.diff().dt.days.dropna())
        .reset_index(drop=True)
    )
    return gaps


def determine_churn_threshold(
    transactions_df: pd.DataFrame,
    percentile: float = 90.0,
) -> dict:
    """
    Derive an implicit churn threshold from the purchase-gap distribution.

    The threshold is the Nth percentile of all inter-purchase gaps.
    """
    gaps = compute_purchase_gaps(transactions_df).dropna()

    threshold_days = float(np.percentile(gaps, percentile))
    return {
        "threshold_days":  threshold_days,
        "percentile_used": percentile,
        "mean_gap":        float(gaps.mean()),
        "median_gap":      float(gaps.median()),
        "std_gap":         float(gaps.std()),
        "n_gaps_analyzed": int(len(gaps)),
    }


def label_churn(
    transactions_df: pd.DataFrame,
    snapshot_date: pd.Timestamp = None,
    threshold_days: float = None,
) -> pd.DataFrame:
    """
    Assign implicit churn labels to each customer.

    A customer is considered churned if their days since last purchase
    exceeds threshold_days.

    Returns
    -------
    DataFrame: customer_id, last_purchase_date, days_since_last,
               threshold_days, churned (bool), churn_label
    """
    df = transactions_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    if snapshot_date is None:
        snapshot_date = df["transaction_date"].max() + timedelta(days=1)

    if threshold_days is None:
        threshold_info = determine_churn_threshold(df)
        threshold_days = threshold_info["threshold_days"]

    last_purchase = (
        df.groupby("customer_id")["transaction_date"]
        .max()
        .reset_index()
        .rename(columns={"transaction_date": "last_purchase_date"})
    )

    last_purchase["days_since_last"] = (
        snapshot_date - last_purchase["last_purchase_date"]
    ).dt.days

    last_purchase["threshold_days"] = threshold_days
    last_purchase["churned"]        = last_purchase["days_since_last"] > threshold_days
    last_purchase["churn_label"]    = last_purchase["churned"].map(
        {True: "Churned", False: "Active"}
    )

    return last_purchase


def compute_churn_stats(churn_df: pd.DataFrame) -> dict:
    """
    Summarise churn counts and rate from the output of label_churn.
    """
    total    = int(len(churn_df))
    churned  = int(churn_df["churned"].sum())
    active   = total - churned
    rate     = churned / total if total > 0 else 0.0
    threshold = float(churn_df["threshold_days"].iloc[0]) if total > 0 else 0.0

    return {
        "total_customers":    total,
        "churned":            churned,
        "active":             active,
        "churn_rate":         rate,
        "threshold_days_used": threshold,
    }


if __name__ == "__main__":
    np.random.seed(42)
    customers = [f"C{i}" for i in range(300)]
    df = pd.DataFrame({
        "customer_id":      np.random.choice(customers, 1500),
        "transaction_date": pd.date_range("2021-01-01", periods=1500, freq="8h"),
        "price":            np.random.uniform(10, 150, 1500),
    })

    threshold = determine_churn_threshold(df)
    print("Churn threshold:", threshold["threshold_days"], "days")

    churn_df = label_churn(df)
    stats_   = compute_churn_stats(churn_df)
    print("Churn rate:", f"{stats_['churn_rate']:.1%}")
    print("Churn labeller OK")
