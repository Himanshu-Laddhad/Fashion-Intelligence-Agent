import numpy as np
import pandas as pd
from datetime import timedelta

_EMPTY_COLS = [
    "customer_id", "recency", "frequency", "monetary",
    "r_score", "f_score", "m_score", "rfm_string", "rfm_score", "segment",
]


def compute_rfm(
    transactions_df: pd.DataFrame,
    snapshot_date: pd.Timestamp = None,
) -> pd.DataFrame:
    """
    Compute Recency, Frequency, Monetary values per customer.

    Parameters
    ----------
    transactions_df : DataFrame with columns customer_id, transaction_date, price
    snapshot_date   : Reference date for recency calculation.
                      Defaults to max(transaction_date) + 1 day.

    Returns
    -------
    DataFrame with columns: customer_id, recency (days), frequency, monetary
    """
    if transactions_df.empty:
        return pd.DataFrame(columns=["customer_id", "recency", "frequency", "monetary"])

    df = transactions_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    if snapshot_date is None:
        snapshot_date = df["transaction_date"].max() + timedelta(days=1)

    rfm = (
        df.groupby("customer_id")
        .agg(
            recency=("transaction_date", lambda x: (snapshot_date - x.max()).days),
            frequency=("transaction_date", "count"),
            monetary=("price", "sum"),
        )
        .reset_index()
    )
    return rfm


def score_rfm(rfm_df: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
    """
    Assign 1-5 quantile scores to each RFM dimension.

    Recency is scored in reverse (lower days → higher score).
    Ties are broken with method='first'.

    Adds: r_score, f_score, m_score, rfm_string, rfm_score.
    """
    if rfm_df.empty:
        return rfm_df.copy()

    df = rfm_df.copy()
    n = len(df)
    labels = list(range(1, n_quantiles + 1))

    def _quantile_score(series: pd.Series, ascending: bool) -> pd.Series:
        """Rank into n_quantiles bins; ascending=True → larger value = larger bin."""
        ranked = series.rank(method="first", ascending=ascending)
        # Map rank to 1..n_quantiles
        return pd.cut(
            ranked,
            bins=n_quantiles,
            labels=labels,
        ).astype(int)

    # Recency: lower days = higher score → rank ascending (low rank = low value)
    # then invert so score 5 = lowest recency days
    r_rank = df["recency"].rank(method="first", ascending=True)
    df["r_score"] = pd.cut(r_rank, bins=n_quantiles, labels=labels).astype(int)
    df["r_score"] = (n_quantiles + 1) - df["r_score"]   # invert

    # Frequency and Monetary: higher = better
    df["f_score"] = _quantile_score(df["frequency"], ascending=True)
    df["m_score"] = _quantile_score(df["monetary"],  ascending=True)

    df["rfm_string"] = (
        df["r_score"].astype(str)
        + df["f_score"].astype(str)
        + df["m_score"].astype(str)
    )
    df["rfm_score"] = (df["r_score"] + df["f_score"] + df["m_score"]) / 3.0

    return df


def label_segments(scored_rfm_df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign a human-readable segment label based on r/f/m score patterns.

    Segments (evaluated in priority order):
        Champions           r=5, f≥4
        Loyal Customers     r≥4, f≥3
        Big Spenders        r≥3, f≤2, m≥4
        Potential Loyalists r≥3, f≥2
        New Customers       r=5, f=1
        At Risk             r≤2, f≥4
        Churned             r≤2, f≤2
        Needs Attention     (all others)
    """
    if scored_rfm_df.empty:
        return scored_rfm_df.copy()

    df = scored_rfm_df.copy()
    r, f, m = df["r_score"], df["f_score"], df["m_score"]

    conditions = [
        (r == 5) & (f >= 4),
        (r >= 4) & (f >= 3),
        (r >= 3) & (f <= 2) & (m >= 4),
        (r >= 3) & (f >= 2),
        (r == 5) & (f == 1),
        (r <= 2) & (f >= 4),
        (r <= 2) & (f <= 2),
    ]
    choices = [
        "Champions",
        "Loyal Customers",
        "Big Spenders",
        "Potential Loyalists",
        "New Customers",
        "At Risk",
        "Churned",
    ]

    df["segment"] = np.select(conditions, choices, default="Needs Attention")
    return df


def build_rfm_pipeline(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full RFM pipeline: compute → score → label.

    Returns empty DataFrame with correct column names if input is empty.
    """
    if transactions_df.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    rfm      = compute_rfm(transactions_df)
    scored   = score_rfm(rfm)
    labelled = label_segments(scored)
    return labelled


if __name__ == "__main__":
    np.random.seed(42)
    n         = 1000
    customers = [f"C{i}" for i in range(200)]
    df        = pd.DataFrame({
        "customer_id":      np.random.choice(customers, n),
        "transaction_date": pd.date_range("2022-01-01", periods=n, freq="6h"),
        "price":            np.random.uniform(10, 200, n),
    })

    result = build_rfm_pipeline(df)
    print("RFM shape:", result.shape)
    print("Segments:", result["segment"].value_counts().to_dict())
    print("RFM pipeline OK")
