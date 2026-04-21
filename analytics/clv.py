import warnings
import numpy as np
import pandas as pd
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data

warnings.filterwarnings("ignore")


def prepare_lifetimes_df(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw transactions to the summary format expected by lifetimes models.

    Returns empty DataFrame if input is empty or has fewer than 50 unique customers.
    """
    if transactions_df is None or transactions_df.empty:
        return pd.DataFrame()

    n_customers = transactions_df["customer_id"].nunique()
    if n_customers < 50:
        return pd.DataFrame()

    df = transactions_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    observation_end = df["transaction_date"].max()

    summary = summary_data_from_transaction_data(
        df,
        customer_id_col="customer_id",
        datetime_col="transaction_date",
        monetary_value_col="price",
        observation_period_end=observation_end,
    )
    return summary


def fit_bgnbd(summary_df: pd.DataFrame) -> BetaGeoFitter:
    """Fit and return a BG/NBD model on the lifetimes summary DataFrame."""
    bgf = BetaGeoFitter(penalizer_coef=0.01)
    bgf.fit(summary_df["frequency"], summary_df["recency"], summary_df["T"])
    return bgf


def fit_gamma_gamma(summary_df: pd.DataFrame) -> GammaGammaFitter:
    """
    Fit and return a Gamma-Gamma monetary model.

    Only customers with at least one repeat purchase are used.
    """
    repeat = summary_df[summary_df["frequency"] > 0]
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(repeat["frequency"], repeat["monetary_value"])
    return ggf


def compute_clv(
    summary_df: pd.DataFrame,
    bgnbd_model: BetaGeoFitter,
    gg_model: GammaGammaFitter,
    months: int = 12,
    discount_rate: float = 0.01,
) -> pd.DataFrame:
    """
    Compute 12-month CLV for each customer.

    Returns summary_df augmented with predicted_purchases and clv columns.
    """
    df = summary_df.copy()

    # Predicted repeat purchases over the forecast horizon (in days)
    t_days = months * 30
    df["predicted_purchases"] = bgnbd_model.conditional_expected_number_of_purchases_up_to_time(
        t_days,
        df["frequency"],
        df["recency"],
        df["T"],
    )

    # CLV — requires customers with at least one repeat purchase for GG model
    # lifetimes API: pass each column as a separate Series argument
    repeat_mask  = df["frequency"] > 0
    repeat_df    = df[repeat_mask]
    clv_series = gg_model.customer_lifetime_value(
        bgnbd_model,
        repeat_df["frequency"],
        repeat_df["recency"],
        repeat_df["T"],
        repeat_df["monetary_value"],
        time=months,
        discount_rate=discount_rate,
        freq="M",
    )

    df["clv"] = 0.0
    df.loc[clv_series.index, "clv"] = clv_series.values

    return df


def run_clv_analysis(transactions_df: pd.DataFrame) -> dict:
    """
    Full CLV pipeline: prepare → BG/NBD → Gamma-Gamma → CLV computation.

    Returns {"available": False, "reason": str} on failure or insufficient data.
    """
    try:
        summary_df = prepare_lifetimes_df(transactions_df)

        if summary_df is None or summary_df.empty:
            return {"available": False, "reason": "insufficient data (< 50 customers)"}

        bgnbd_model = fit_bgnbd(summary_df)
        gg_model    = fit_gamma_gamma(summary_df)
        clv_df      = compute_clv(summary_df, bgnbd_model, gg_model)

        clv_vals = clv_df["clv"]
        percentiles = {
            "p25": float(clv_vals.quantile(0.25)),
            "p50": float(clv_vals.quantile(0.50)),
            "p75": float(clv_vals.quantile(0.75)),
            "p90": float(clv_vals.quantile(0.90)),
        }

        return {
            "available":           True,
            "clv_df":              clv_df,
            "total_predicted_clv": float(clv_vals.sum()),
            "clv_percentiles":     percentiles,
            "n_customers":         int(len(clv_df)),
        }

    except Exception as exc:
        return {"available": False, "reason": str(exc)}


if __name__ == "__main__":
    np.random.seed(42)
    customers = [f"C{i}" for i in range(300)]
    df = pd.DataFrame({
        "customer_id":      np.random.choice(customers, 1500),
        "transaction_date": pd.date_range("2021-01-01", periods=1500, freq="6h"),
        "price":            np.abs(np.random.normal(50, 20, 1500)),
    })

    result = run_clv_analysis(df)
    print("CLV available:", result["available"])
    if result["available"]:
        print("Median 12m CLV:", result["clv_percentiles"]["p50"])
        print("Total predicted CLV:", f"${result['total_predicted_clv']:,.0f}")
    else:
        print("Reason:", result.get("reason"))
    print("CLV module OK")
