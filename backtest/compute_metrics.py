"""
Step 3 — Compute backtest metrics from scored time series.

For each query:
- Finds the first week in the predicted year where direction == 'rising'
- Compares against the confirmed label (ground truth)
- Computes lead time as weeks between first 'rising' flag and the actual
  peak week in the raw series (max interest value within the predicted year)
- Falls back to a data-cutoff date for 2026 where the year is incomplete
- Builds confusion matrix and prints classification report

Saves backtest/results/metrics.csv and backtest/results/summary.txt

Usage:
    python -m backtest.compute_metrics
"""

import sys
from pathlib import Path

import pandas as pd

CSV_PATH = Path("pinterest_predicts_fashion_labeled.csv")
RAW_DIR = Path("backtest/data/raw")
SCORED_DIR = Path("backtest/data/scored")
RESULTS_DIR = Path("backtest/results")

DATA_CUTOFF = {2026: "2026-04-30"}


def first_rising_week(scored_df: pd.DataFrame) -> pd.Timestamp | None:
    rising = scored_df[scored_df["direction"] == "rising"]
    return rising.index[0] if not rising.empty else None


def actual_peak_week(query: str, predicted_year: int) -> pd.Timestamp | None:
    """Find the week with highest interest within the predicted year from raw series."""
    safe_name = query.replace(" ", "_").replace("/", "-")
    raw_path = RAW_DIR / f"{safe_name}.csv"
    if not raw_path.exists():
        return None
    raw = pd.read_csv(raw_path, index_col=0, parse_dates=True)
    raw.columns = ["interest"]
    year_end = DATA_CUTOFF.get(predicted_year, f"{predicted_year}-12-31")
    year_data = raw.loc[str(predicted_year):year_end]
    if year_data.empty:
        return None
    return year_data["interest"].idxmax()


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    labeled = pd.read_csv(CSV_PATH)

    records = []

    for _, row in labeled.iterrows():
        query = row["query"]
        predicted_year = int(row["predicted_year"])
        confirmed = str(row["confirmed"]).upper() == "TRUE"
        safe_name = query.replace(" ", "_").replace("/", "-")
        scored_path = SCORED_DIR / f"{safe_name}.csv"

        if not scored_path.exists():
            records.append(
                {
                    "query": query,
                    "predicted_year": predicted_year,
                    "confirmed": confirmed,
                    "first_rising_date": None,
                    "peak_date": None,
                    "lead_weeks": None,
                    "scorer_flagged_rising": False,
                    "tp": False,
                    "tn": False,
                    "fp": False,
                    "fn": False,
                    "data_available": False,
                }
            )
            continue

        scored = pd.read_csv(scored_path, index_col=0, parse_dates=True)
        first_rising = first_rising_week(scored)
        flagged = first_rising is not None

        peak = actual_peak_week(query, predicted_year)
        lead_weeks = None
        if flagged and peak is not None and first_rising <= peak:
            lead_weeks = (peak - first_rising).days / 7
        elif flagged and peak is not None and first_rising > peak:
            # Scorer fired after peak — negative lead time (lagging signal)
            lead_weeks = (peak - first_rising).days / 7

        tp = confirmed and flagged
        tn = (not confirmed) and (not flagged)
        fp = (not confirmed) and flagged
        fn = confirmed and (not flagged)

        records.append(
            {
                "query": query,
                "predicted_year": predicted_year,
                "confirmed": confirmed,
                "first_rising_date": first_rising,
                "peak_date": peak,
                "lead_weeks": round(lead_weeks, 1) if lead_weeks is not None else None,
                "scorer_flagged_rising": flagged,
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "data_available": True,
            }
        )

    metrics_df = pd.DataFrame(records)
    metrics_df.to_csv(RESULTS_DIR / "metrics.csv", index=False)

    available = metrics_df[metrics_df["data_available"]]
    tp = available["tp"].sum()
    tn = available["tn"].sum()
    fp = available["fp"].sum()
    fn = available["fn"].sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / len(available) if len(available) > 0 else 0

    # Lead time against actual peak (positive = flagged before peak, negative = lagging)
    rising_queries = available[available["scorer_flagged_rising"] & available["lead_weeks"].notna()]
    early_queries = rising_queries[rising_queries["lead_weeks"] >= 0]
    avg_lead = early_queries["lead_weeks"].mean() if not early_queries.empty else 0
    median_lead = early_queries["lead_weeks"].median() if not early_queries.empty else 0
    lagging = (rising_queries["lead_weeks"] < 0).sum()

    # Split by year for partial-data note on 2026
    by_year = available.groupby("predicted_year").apply(
        lambda g: pd.Series(
            {
                "n": len(g),
                "tp": g["tp"].sum(),
                "tn": g["tn"].sum(),
                "fp": g["fp"].sum(),
                "fn": g["fn"].sum(),
                "accuracy": (g["tp"].sum() + g["tn"].sum()) / len(g),
            }
        )
    )

    summary = f"""
=== Pinterest Predicts Backtest — Momentum Scorer Validation ===

Queries evaluated : {len(available)} / {len(metrics_df)}
Queries skipped   : {len(metrics_df) - len(available)} (no Trends data returned)

Confusion matrix (all years):
  TP (confirmed + flagged rising) : {tp}
  TN (not confirmed + not flagged): {tn}
  FP (not confirmed + flagged)    : {fp}
  FN (confirmed + not flagged)    : {fn}

Classification metrics:
  Precision : {precision:.2f}
  Recall    : {recall:.2f}
  F1        : {f1:.2f}
  Accuracy  : {accuracy:.2f}

Lead time vs actual peak week (confirmed-rising queries only):
  Flagged before peak : {len(early_queries)} queries
  Flagged after peak  : {lagging} queries (lagging signal)
  Mean lead time      : {avg_lead:.1f} weeks
  Median lead time    : {median_lead:.1f} weeks

Per-year breakdown:
{by_year.to_string()}

Note: 2026 rows use April 2026 as data cutoff. Lead times are lower bounds.
      Lead time is measured from first 'rising' flag to actual peak interest week.
"""

    print(summary)
    with open(RESULTS_DIR / "summary.txt", "w") as f:
        f.write(summary)

    print(f"Saved: {RESULTS_DIR / 'metrics.csv'}")
    print(f"Saved: {RESULTS_DIR / 'summary.txt'}")


if __name__ == "__main__":
    main()
