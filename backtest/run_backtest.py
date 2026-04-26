"""
Full backtest pipeline — runs all steps in order.

Usage:
    python -m backtest.run_backtest

Steps:
    1. fetch_trends      — pull Google Trends series for all 32 queries
    2. sliding_window_scorer — score each series across a weekly sliding window
    3. compute_metrics   — confusion matrix, precision/recall, lead times
    4. visualize         — spaghetti chart + lead time bar chart
"""

from backtest import fetch_trends, sliding_window_scorer, compute_metrics, visualize

if __name__ == "__main__":
    print("\n=== Step 1: Fetching Google Trends data ===\n")
    fetch_trends.main()

    print("\n=== Step 2: Running sliding window scorer ===\n")
    sliding_window_scorer.main()

    print("\n=== Step 3: Computing metrics ===\n")
    compute_metrics.main()

    print("\n=== Step 4: Generating visualizations ===\n")
    visualize.main()

    print("\nBacktest complete. Results in backtest/results/")
