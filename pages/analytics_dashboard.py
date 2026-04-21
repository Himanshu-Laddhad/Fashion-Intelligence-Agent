import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from database.db_manager import DatabaseManager

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Helper ────────────────────────────────────────────────────────────────────

def _read(sql: str) -> pd.DataFrame:
    """Execute SQL against the DuckDB file and return a DataFrame."""
    with DatabaseManager() as db:
        return db.conn.execute(sql).df()


def _safe_read(sql: str, label: str) -> pd.DataFrame | None:
    """Wrap _read with a st.warning fallback on any error."""
    try:
        return _read(sql)
    except Exception as exc:
        st.warning(f"⚠️ Could not load {label}: {exc}")
        return None


# ── 1. Header ─────────────────────────────────────────────────────────────────

st.title("📊 Fashion Intelligence Analytics Dashboard")
st.caption("Live metrics from DuckDB — updates on each query run")

st.divider()

# ── 2. Trend Velocity Index History ───────────────────────────────────────────

st.subheader("📈 Trend Velocity Index History")

tvi_df = _safe_read(
    "SELECT * FROM trend_scores ORDER BY scored_at DESC LIMIT 100",
    "TVI scores",
)

if tvi_df is None or tvi_df.empty:
    st.info("No TVI data yet. Run a query in the main app.")
else:
    latest = tvi_df.iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Latest TVI Score", f"{latest.get('tvi_score', 0):.1f} / 100")
    col2.metric("Confidence", str(latest.get("confidence", "—")).capitalize())
    col3.metric("Total Queries Tracked", tvi_df["query"].nunique())

    fig = px.line(
        tvi_df.sort_values("scored_at"),
        x="scored_at",
        y="tvi_score",
        color="query",
        title="TVI Score Over Time",
        labels={"scored_at": "Scored At", "tvi_score": "TVI Score", "query": "Query"},
        markers=True,
    )
    fig.update_layout(yaxis_range=[0, 100], height=350)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 3. Query Frequency Table ──────────────────────────────────────────────────

st.subheader("🔍 Query Frequency")

if tvi_df is not None and not tvi_df.empty:
    freq_df = (
        tvi_df.groupby("query")
        .agg(runs=("tvi_score", "count"), avg_tvi=("tvi_score", "mean"))
        .reset_index()
        .sort_values("runs", ascending=False)
        .rename(columns={"query": "Query", "runs": "Runs", "avg_tvi": "Avg TVI"})
    )
    freq_df["Avg TVI"] = freq_df["Avg TVI"].round(2)
    st.dataframe(freq_df, use_container_width=True, hide_index=True)
else:
    st.info("No query data available yet.")

st.divider()

# ── 4. Data Sources Health ────────────────────────────────────────────────────

st.subheader("🌐 Data Sources Health")

snap_df = _safe_read(
    "SELECT * FROM trend_snapshots ORDER BY timestamp DESC",
    "trend snapshots",
)

if snap_df is not None and not snap_df.empty:
    health_df = (
        snap_df.groupby("source")
        .agg(
            total_snapshots=("id", "count"),
            last_updated=("timestamp", "max"),
            total_items=("item_count", "sum"),
        )
        .reset_index()
        .rename(columns={
            "source": "Source",
            "total_snapshots": "Snapshots",
            "last_updated": "Last Updated",
            "total_items": "Total Items",
        })
        .sort_values("Last Updated", ascending=False)
    )
    st.dataframe(health_df, use_container_width=True, hide_index=True)
else:
    st.info("No scrape data recorded yet.")

st.divider()

# ── 5. Customer Intelligence ──────────────────────────────────────────────────

st.subheader("👥 Customer Segments (H&M Dataset)")

seg_df = _safe_read("SELECT * FROM customer_segments", "customer segments")

if seg_df is None or seg_df.empty:
    st.warning("Run customer analysis first. H&M data required in data/hm/")
else:
    col_a, col_b = st.columns(2)

    with col_a:
        if "cluster_label" in seg_df.columns:
            pie_data = seg_df["cluster_label"].value_counts().reset_index()
            pie_data.columns = ["Segment", "Count"]
            fig_pie = px.pie(
                pie_data,
                names="Segment",
                values="Count",
                title="Customer Segment Distribution",
                hole=0.35,
            )
            fig_pie.update_layout(height=380)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No cluster_label column in customer_segments.")

    with col_b:
        x_col = "recency_days" if "recency_days" in seg_df.columns else None
        y_col = "monetary" if "monetary" in seg_df.columns else None
        c_col = "cluster_label" if "cluster_label" in seg_df.columns else None

        if x_col and y_col:
            fig_scatter = px.scatter(
                seg_df,
                x=x_col,
                y=y_col,
                color=c_col,
                title="Monetary Value vs Recency",
                labels={
                    x_col: "Recency (days)",
                    y_col: "Monetary Value",
                    c_col: "Segment",
                },
                opacity=0.65,
            )
            fig_scatter.update_layout(height=380)
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Recency / monetary columns not available.")

st.divider()

# ── 6. Model Registry ─────────────────────────────────────────────────────────

st.subheader("🗂️ Model Registry")

model_df = _safe_read(
    "SELECT * FROM model_registry ORDER BY trained_at DESC",
    "model registry",
)

if model_df is not None and not model_df.empty:
    st.dataframe(model_df, use_container_width=True, hide_index=True)
else:
    st.info("No models registered yet.")

st.divider()

# ── Refresh ───────────────────────────────────────────────────────────────────

if st.button("🔄 Refresh Data"):
    st.rerun()
