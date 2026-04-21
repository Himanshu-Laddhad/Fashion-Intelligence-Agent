import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats


def run_mann_kendall(timeseries_df: pd.DataFrame, alpha: float = 0.05) -> dict:
    """
    Run Mann-Kendall trend test on the first numeric column of timeseries_df.

    Returns significance, p-value, direction, slope, and Kendall's Tau.
    """
    numeric_cols = [
        c for c in timeseries_df.columns
        if pd.api.types.is_numeric_dtype(timeseries_df[c])
    ]
    if not numeric_cols:
        return {"significant": False, "reason": "no numeric column", "p_value": None}

    series = timeseries_df[numeric_cols[0]].dropna().tolist()

    if len(series) < 10:
        return {"significant": False, "reason": "insufficient data", "p_value": None}

    result = mk.original_test(series)

    return {
        "significant": bool(result.p <= alpha),
        "p_value":     float(result.p),
        "trend":       str(result.trend),
        "slope":       float(result.slope),
        "tau":         float(result.Tau),
        "alpha_used":  alpha,
    }


def run_t_test_vs_baseline(
    recent_series: pd.Series, baseline_series: pd.Series
) -> dict:
    """
    Independent two-sample t-test comparing recent vs baseline values.

    Returns test statistic, p-value, significance flag, and direction.
    """
    t_stat, p_value = stats.ttest_ind(
        recent_series.dropna(), baseline_series.dropna()
    )
    return {
        "statistic": float(t_stat),
        "p_value":   float(p_value),
        "significant": bool(p_value < 0.05),
        "direction": "recent_higher" if t_stat > 0 else "baseline_higher",
    }


def compute_descriptive_stats(series: pd.Series) -> dict:
    """Return common descriptive statistics including coefficient of variation."""
    clean = series.dropna()
    mean  = float(clean.mean())
    std   = float(clean.std())
    cv    = float(std / mean) if mean != 0 else float("nan")

    return {
        "mean":   mean,
        "median": float(clean.median()),
        "std":    std,
        "q25":    float(clean.quantile(0.25)),
        "q75":    float(clean.quantile(0.75)),
        "min":    float(clean.min()),
        "max":    float(clean.max()),
        "cv":     cv,
    }


def test_trend_significance(timeseries_df: pd.DataFrame) -> dict:
    """
    Comprehensive significance testing on a trend time series.

    Runs:
      - Mann-Kendall test (full series)
      - Independent t-test (first half vs second half)
      - Descriptive statistics (full series)
    """
    numeric_cols = [
        c for c in timeseries_df.columns
        if pd.api.types.is_numeric_dtype(timeseries_df[c])
    ]

    mk_result = run_mann_kendall(timeseries_df)

    if numeric_cols:
        full_series = timeseries_df[numeric_cols[0]].dropna().reset_index(drop=True)
        mid         = len(full_series) // 2
        baseline    = full_series.iloc[:mid]
        recent      = full_series.iloc[mid:]
        t_result    = run_t_test_vs_baseline(recent, baseline)
        desc_result = compute_descriptive_stats(full_series)
    else:
        t_result    = {"statistic": None, "p_value": None, "significant": False,
                       "direction": "unknown"}
        desc_result = {}

    return {
        "mann_kendall": mk_result,
        "t_test":       t_result,
        "descriptive":  desc_result,
    }


if __name__ == "__main__":
    dates = pd.date_range("2022-01-01", periods=52, freq="W")
    vals  = np.linspace(30, 70, 52) + np.random.normal(0, 3, 52)
    df    = pd.DataFrame({"value": vals}, index=dates)

    result = test_trend_significance(df)
    print("MK significant:", result["mann_kendall"]["significant"])
    print("Trend:", result["mann_kendall"]["trend"])
    print("Statistical tests OK")
