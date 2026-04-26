"""
Step 2 — Run the momentum scorer across a sliding window for every query.

For each query, evaluates compute_trend_momentum at every week from
52 weeks before the predicted year through the end of that year.
Saves one CSV per query under backtest/data/scored/.

Usage:
    python -m backtest.sliding_window_scorer
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_sources.google_trends import compute_trend_momentum

CSV_PATH = Path("pinterest_predicts_fashion_labeled.csv")
RAW_DIR = Path("backtest/data/raw")
OUT_DIR = Path("backtest/data/scored")

# Year-end cutoff — 2026 data only goes to April
YEAR_END = {2024: "2024-12-31", 2025: "2025-12-31", 2026: "2026-04-30"}


def score_query(query: str, predicted_year: int) -> pd.DataFrame:
    safe_name = query.replace(" ", "_").replace("/", "-")
    raw_path = RAW_DIR / f"{safe_name}.csv"
    if not raw_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(raw_path, index_col=0, parse_dates=True)
    df.columns = [query]

    window_start = pd.Timestamp(f"{predicted_year - 1}-01-01")
    window_end = pd.Timestamp(YEAR_END.get(predicted_year, f"{predicted_year}-12-31"))

    # Trim to evaluation window
    eval_series = df.loc[window_start:window_end]
    if len(eval_series) < 10:
        return pd.DataFrame()

    records = []
    # Evaluate at each week in the predicted year
    eval_dates = eval_series.loc[str(predicted_year):].index

    for current_date in eval_dates:
        # Use all data up to and including current_date as the "live" window
        historical_df = df.loc[:current_date].copy()
        historical_df.columns = [query]
        result = compute_trend_momentum(historical_df)
        records.append(
            {
                "date": current_date,
                "momentum": result["momentum"],
                "direction": result["direction"],
                "recent_avg": result["recent_avg"],
                "historical_avg": result["historical_avg"],
            }
        )

    return pd.DataFrame(records).set_index("date")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    labeled = pd.read_csv(CSV_PATH)

    total = len(labeled)
    for i, row in labeled.iterrows():
        query = row["query"]
        predicted_year = int(row["predicted_year"])
        safe_name = query.replace(" ", "_").replace("/", "-")
        out_path = OUT_DIR / f"{safe_name}.csv"

        if out_path.exists():
            print(f"[{i+1}/{total}] skip  {query}")
            continue

        print(f"[{i+1}/{total}] score {query} ...", end=" ", flush=True)
        scored = score_query(query, predicted_year)
        if scored.empty:
            print("no data")
        else:
            scored.to_csv(out_path)
            print(f"{len(scored)} weekly evaluations")


if __name__ == "__main__":
    main()
