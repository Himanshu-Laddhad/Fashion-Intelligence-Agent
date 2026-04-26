"""
Step 4 — Generate backtest visualizations.

Chart 1: Spaghetti chart
  - One line per confirmed-rising query (2024 + 2025 only, full-year data)
  - X-axis: weeks relative to peak proxy (negative = before peak)
  - Y-axis: momentum score
  - Dashed horizontal line at 0.1 (rising threshold)

Chart 2: Lead time bar chart
  - One bar per confirmed-rising query
  - Bar height = weeks before peak proxy scorer first flagged 'rising'
  - Sorted descending

Saves both to backtest/results/

Usage:
    python -m backtest.visualize
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

METRICS_CSV = Path("backtest/results/metrics.csv")
SCORED_DIR = Path("backtest/data/scored")
RESULTS_DIR = Path("backtest/results")

PEAK_PROXY = {2024: "2024-07-01", 2025: "2025-07-01", 2026: "2026-04-30"}


def load_scored(query: str) -> pd.DataFrame:
    safe_name = query.replace(" ", "_").replace("/", "-")
    path = SCORED_DIR / f"{safe_name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, index_col=0, parse_dates=True)


def spaghetti_chart(metrics_df: pd.DataFrame) -> None:
    # Only full-year confirmed queries for clean lines
    subset = metrics_df[
        metrics_df["confirmed"]
        & metrics_df["data_available"]
        & metrics_df["predicted_year"].isin([2024, 2025])
    ]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_facecolor("#0f0f0f")
    fig.patch.set_facecolor("#0f0f0f")

    color_map = {2024: "#4fc3f7", 2025: "#f06292"}

    for _, row in subset.iterrows():
        scored = load_scored(row["query"])
        if scored.empty:
            continue
        peak = pd.Timestamp(PEAK_PROXY[row["predicted_year"]])
        # Convert dates to weeks-relative-to-peak
        weeks_rel = ((scored.index - peak).days / 7).round(0).astype(int)
        color = color_map.get(row["predicted_year"], "#ffffff")
        ax.plot(
            weeks_rel,
            scored["momentum"],
            color=color,
            alpha=0.55,
            linewidth=1.4,
            label=f"{row['query']} ({row['predicted_year']})",
        )

    ax.axhline(0.1, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.6,
               label="Rising threshold (0.1)")
    ax.axhline(0.0, color="#555555", linewidth=0.6, linestyle="-")
    ax.axvline(0, color="#aaaaaa", linewidth=0.8, linestyle=":", alpha=0.5, label="Peak proxy")

    ax.set_xlim(-52, 26)
    ax.set_xlabel("Weeks relative to peak", color="#cccccc", fontsize=11)
    ax.set_ylabel("Momentum score", color="#cccccc", fontsize=11)
    ax.set_title("Momentum Score vs. Peak — Confirmed Rising Trends (2024–2025)",
                 color="#ffffff", fontsize=13, pad=14)
    ax.tick_params(colors="#999999")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")

    legend = ax.legend(
        fontsize=7, loc="upper left", framealpha=0.2,
        labelcolor="#cccccc", facecolor="#1a1a1a", edgecolor="#333333",
        ncol=2,
    )

    plt.tight_layout()
    out = RESULTS_DIR / "spaghetti_chart.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {out}")


def lead_time_chart(metrics_df: pd.DataFrame) -> None:
    subset = metrics_df[
        metrics_df["confirmed"]
        & metrics_df["data_available"]
        & metrics_df["lead_weeks"].notna()
        & metrics_df["predicted_year"].isin([2024, 2025])
    ].copy()

    subset = subset.sort_values("lead_weeks", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(4, len(subset) * 0.45)))
    ax.set_facecolor("#0f0f0f")
    fig.patch.set_facecolor("#0f0f0f")

    color_map = {2024: "#4fc3f7", 2025: "#f06292"}
    colors = [color_map.get(y, "#aaaaaa") for y in subset["predicted_year"]]

    bars = ax.barh(
        subset["query"],
        subset["lead_weeks"],
        color=colors,
        edgecolor="#1a1a1a",
        height=0.6,
    )

    for bar, val in zip(bars, subset["lead_weeks"]):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}w",
            va="center",
            color="#cccccc",
            fontsize=8,
        )

    avg = subset["lead_weeks"].mean()
    ax.axvline(avg, color="#ffffff", linewidth=1.0, linestyle="--", alpha=0.7,
               label=f"Mean lead: {avg:.1f} weeks")

    ax.set_xlabel("Weeks before peak scorer first flagged 'rising'", color="#cccccc", fontsize=10)
    ax.set_title("Lead Time by Query — Confirmed Rising Trends (2024–2025)",
                 color="#ffffff", fontsize=12, pad=12)
    ax.tick_params(colors="#999999")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")
    ax.legend(fontsize=9, labelcolor="#cccccc", facecolor="#1a1a1a",
              edgecolor="#333333", framealpha=0.3)

    # Year legend patches
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4fc3f7", label="2024"),
        Patch(facecolor="#f06292", label="2025"),
    ]
    ax.legend(handles=legend_elements + ax.get_legend_handles_labels()[0][1:],
              fontsize=9, labelcolor="#cccccc", facecolor="#1a1a1a",
              edgecolor="#333333", framealpha=0.3)

    plt.tight_layout()
    out = RESULTS_DIR / "lead_time_chart.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {out}")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not METRICS_CSV.exists():
        print("metrics.csv not found — run compute_metrics.py first")
        return

    metrics_df = pd.read_csv(METRICS_CSV)
    metrics_df["data_available"] = metrics_df["data_available"].astype(bool)
    metrics_df["confirmed"] = metrics_df["confirmed"].astype(bool)
    metrics_df["first_rising_date"] = pd.to_datetime(metrics_df["first_rising_date"], errors="coerce")

    spaghetti_chart(metrics_df)
    lead_time_chart(metrics_df)


if __name__ == "__main__":
    main()
