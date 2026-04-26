"""
Step 1 — Batch-fetch Google Trends time series for every query in the
Pinterest Predicts labeled dataset.

Saves one CSV per query under backtest/data/raw/.
Skips queries that already have a saved file (safe to re-run).

Usage:
    python -m backtest.fetch_trends
"""

import sys
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

CSV_PATH = Path("pinterest_predicts_fashion_labeled.csv")
OUT_DIR = Path("backtest/data/raw")
# Pull 5 years of weekly data so every predicted_year has a full baseline.
TIMEFRAME = "2019-01-01 2026-04-30"

# Shorter fallback queries for terms pytrends can't resolve at full length.
# The raw file is still saved under the original query's safe name.
QUERY_OVERRIDES = {
    "big hair accessories": "hair accessories",
    "fisherman aesthetic outfit": "fisherman aesthetic",
    "moto boho outfit": "moto boho",
    "poet core aesthetic": "poetcore",
    "brooch men suit": "brooch outfit",
    "ice blue aesthetic outfit": "ice blue fashion",
    "vamp romantic aesthetic": "vamp aesthetic",
    "glitchy glam makeup": "glitch makeup",
    "gummy accessories aesthetic": "gummy jewelry",
    "alien core aesthetic outfit": "aliencore",
    "fairycore woodland outfit": "fairycore",
}


def fetch(query: str) -> pd.DataFrame:
    pt = TrendReq(hl="en-US", tz=360)
    pt.build_payload([query], cat=0, timeframe=TIMEFRAME, geo="", gprop="")
    time.sleep(3)  # avoid rate-limit
    df = pt.interest_over_time()
    if df.empty:
        return df
    df = df.drop(columns=["isPartial"], errors="ignore")
    df.index = pd.to_datetime(df.index)
    df.columns = ["interest"]
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    labeled = pd.read_csv(CSV_PATH)

    total = len(labeled)
    for i, row in labeled.iterrows():
        query = row["query"]
        safe_name = query.replace(" ", "_").replace("/", "-")
        out_path = OUT_DIR / f"{safe_name}.csv"

        if out_path.exists():
            print(f"[{i+1}/{total}] skip  {query}")
            continue

        fetch_query = QUERY_OVERRIDES.get(query, query)
        label = f"{query}" + (f" (as '{fetch_query}')" if fetch_query != query else "")
        print(f"[{i+1}/{total}] fetch {label} ...", end=" ", flush=True)
        try:
            df = fetch(fetch_query)
            if df.empty:
                print("empty — skipped")
            else:
                df.to_csv(out_path)
                print(f"saved {len(df)} rows")
        except Exception as exc:
            print(f"ERROR: {exc}")
            # back off on any error
            time.sleep(10)


if __name__ == "__main__":
    main()
