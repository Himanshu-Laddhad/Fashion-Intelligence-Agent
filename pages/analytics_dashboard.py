"""
Analytics Dashboard — powered by Google Trends (pytrends) + H&M dataset.
Trend data is fetched live from Google Trends; no query-run history required.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from data_sources.google_trends import compute_trend_momentum

try:
    from database.db_manager import DatabaseManager
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────────────────────

PRESET_KEYWORDS = [
    "denim jacket",
    "oversized hoodie",
    "quiet luxury",
    "Y2K fashion",
    "summer dress",
    "wide leg pants",
    "coquette aesthetic",
    "mob wife aesthetic",
    "cargo pants",
    "ballet flats",
]

TIMEFRAME_OPTIONS = {
    "Past 12 months": "today 12-m",
    "Past 5 years": "today 5-y",
    "Past 90 days": "today 3-m",
    "Past 30 days": "today 1-m",
}

# ── Cached pytrends fetchers ──────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_interest_over_time(keywords: tuple, timeframe: str) -> pd.DataFrame:
    """Fetch interest-over-time for up to 5 keywords (cached 1 hour)."""
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload(list(keywords), cat=0, timeframe=timeframe, geo="", gprop="")
        df = pt.interest_over_time()
        time.sleep(1)
        return df
    except Exception as exc:
        st.warning(f"⚠️ pytrends error: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_region_interest(keyword: str, timeframe: str) -> pd.DataFrame:
    """Fetch interest by country for a single keyword (cached 1 hour)."""
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([keyword], cat=0, timeframe=timeframe, geo="", gprop="")
        df = pt.interest_by_region(resolution="COUNTRY", inc_low_vol=False)
        time.sleep(1)
        return df.reset_index()
    except Exception as exc:
        st.warning(f"⚠️ pytrends region error: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_related_queries(keyword: str) -> dict:
    """Fetch rising + top related queries for one keyword (cached 1 hour)."""
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([keyword], cat=0, timeframe="today 12-m", geo="", gprop="")
        time.sleep(1)
        return pt.related_queries()
    except Exception:
        return {}


def _build_momentum_table(ts_df: pd.DataFrame, keywords: list) -> pd.DataFrame:
    """Derive momentum stats from an already-fetched interest-over-time DataFrame."""
    rows = []
    for kw in keywords:
        if kw in ts_df.columns:
            sub = ts_df[[kw]].rename(columns={kw: kw})
            m = compute_trend_momentum(sub)
        else:
            m = {"momentum": 0.0, "direction": "unknown",
                 "recent_avg": 0.0, "historical_avg": 0.0}
        rows.append({
            "Keyword": kw,
            "Direction": m["direction"].capitalize(),
            "Momentum": round(m["momentum"], 3),
            "Recent Avg (0–100)": round(m["recent_avg"], 1),
            "Historical Avg (0–100)": round(m["historical_avg"], 1),
        })
    return pd.DataFrame(rows)


# ── Header ─────────────────────────────────────────────────────────────────────

st.title("📊 Fashion Trend Analytics")
st.caption("Powered by Google Trends (pytrends) — updates live, no query-run dependency")

st.divider()

# ── Sidebar controls ───────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Controls")

    timeframe_label = st.selectbox("Timeframe", list(TIMEFRAME_OPTIONS.keys()), index=0)
    timeframe = TIMEFRAME_OPTIONS[timeframe_label]

    selected_keywords = st.multiselect(
        "Keywords to track (max 5)",
        PRESET_KEYWORDS,
        default=PRESET_KEYWORDS[:4],
        max_selections=5,
    )

    custom_kw = st.text_input("Add custom keyword", placeholder="e.g. trench coat")
    if custom_kw.strip():
        custom_kw = custom_kw.strip()
        if custom_kw not in selected_keywords:
            if len(selected_keywords) < 5:
                selected_keywords.append(custom_kw)
            else:
                st.warning("Max 5 keywords (pytrends limit). Remove one first.")

    st.divider()
    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()

if not selected_keywords:
    st.warning("Select at least one keyword from the sidebar to begin.")
    st.stop()

kw_tuple = tuple(selected_keywords)

# ── 1. Interest Over Time ─────────────────────────────────────────────────────

st.subheader("📈 Interest Over Time")

with st.spinner("Fetching Google Trends data…"):
    ts_df = _fetch_interest_over_time(kw_tuple, timeframe)

if ts_df is not None and not ts_df.empty:
    plot_df = (
        ts_df
        .drop(columns=["isPartial"], errors="ignore")
        .reset_index()
        .melt(id_vars=["date"], var_name="Keyword", value_name="Interest")
    )
    fig = px.line(
        plot_df,
        x="date",
        y="Interest",
        color="Keyword",
        title=f"Google Trends Interest — {timeframe_label}",
        labels={"date": "Date", "Interest": "Interest (0–100)"},
    )
    fig.update_layout(yaxis_range=[0, 100], height=400, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(
        "No trend data returned. Google Trends may be temporarily rate-limiting requests. "
        "Wait a minute and press **🔄 Clear Cache & Refresh**."
    )

st.divider()

# ── 2. Momentum Scorecard ─────────────────────────────────────────────────────

st.subheader("🚀 Trend Momentum Scorecard")

if ts_df is not None and not ts_df.empty:
    mom_df = _build_momentum_table(ts_df, list(selected_keywords))

    direction_icon = {"Rising": "🟢 Rising", "Falling": "🔴 Falling", "Stable": "🟡 Stable", "Unknown": "⚪ Unknown"}
    mom_df["Direction"] = mom_df["Direction"].map(lambda d: direction_icon.get(d, d))

    rising_n  = mom_df["Direction"].str.contains("Rising").sum()
    falling_n = mom_df["Direction"].str.contains("Falling").sum()
    stable_n  = len(mom_df) - rising_n - falling_n

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Rising",  rising_n)
    c2.metric("🟡 Stable",  stable_n)
    c3.metric("🔴 Falling", falling_n)

    st.dataframe(mom_df, use_container_width=True, hide_index=True)

    fig_bar = px.bar(
        mom_df.assign(raw=mom_df["Momentum"]),
        x="Keyword",
        y="raw",
        color="raw",
        color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        range_color=[-1, 1],
        title="Momentum Score per Keyword  (−1 = falling fast · +1 = rising fast)",
        labels={"raw": "Momentum"},
    )
    fig_bar.update_layout(height=320, coloraxis_showscale=False)
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("Momentum data unavailable — trend fetch required first.")

st.divider()

# ── 3. Geographic Interest ────────────────────────────────────────────────────

st.subheader("🌍 Geographic Interest")

geo_kw = st.selectbox("Keyword for map", selected_keywords, key="geo_kw")

with st.spinner(f"Fetching regional data for '{geo_kw}'…"):
    region_df = _fetch_region_interest(geo_kw, timeframe)

if region_df is not None and not region_df.empty:
    region_df.columns = [c.lower() for c in region_df.columns]
    value_col = next((c for c in region_df.columns if c != "geoname"), None)

    if value_col:
        active = region_df[region_df[value_col] > 0]

        fig_map = px.choropleth(
            active,
            locations="geoname",
            locationmode="country names",
            color=value_col,
            color_continuous_scale="Purples",
            title=f"Interest in '{geo_kw}' by Country — {timeframe_label}",
            labels={value_col: "Interest (0–100)"},
        )
        fig_map.update_layout(height=440)
        st.plotly_chart(fig_map, use_container_width=True)

        st.caption("Top 20 countries by interest")
        st.dataframe(
            active.nlargest(20, value_col)
                  .rename(columns={"geoname": "Country", value_col: "Interest"})
                  .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("No regional data available for this keyword / timeframe combination.")

st.divider()

# ── 4. Rising Related Queries ─────────────────────────────────────────────────

st.subheader("🔥 Rising Related Queries")
st.caption("Based on the past 12 months of Google Trends data")

rel_kw = st.selectbox("Keyword for related queries", selected_keywords, key="rel_kw")

with st.spinner(f"Fetching related queries for '{rel_kw}'…"):
    related = _fetch_related_queries(rel_kw)

kw_data = (related or {}).get(rel_kw, {})
col_top, col_rising = st.columns(2)

with col_top:
    st.markdown("**Top Queries**")
    top_df = kw_data.get("top") if kw_data else None
    if top_df is not None and not top_df.empty:
        st.dataframe(top_df.head(10).reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.info("No top queries data available.")

with col_rising:
    st.markdown("**Breakout / Rising Queries**")
    rising_df = kw_data.get("rising") if kw_data else None
    if rising_df is not None and not rising_df.empty:
        st.dataframe(rising_df.head(10).reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.info("No rising queries data available.")

st.divider()

# ── 5. Customer Intelligence (H&M dataset) ────────────────────────────────────

st.subheader("👥 Customer Segments  (H&M Dataset)")

seg_df = pd.DataFrame()
if _DB_AVAILABLE:
    try:
        with DatabaseManager() as db:
            seg_df = db.conn.execute("SELECT * FROM customer_segments").df()
    except Exception as exc:
        st.warning(f"⚠️ Could not load customer segments: {exc}")

if seg_df.empty:
    st.info(
        "No segment data yet. Run `python run_customer_analysis.py` "
        "with H&M data in `data/hm/` to populate this section."
    )
else:
    col_a, col_b = st.columns(2)

    with col_a:
        if "cluster_label" in seg_df.columns:
            pie_data = seg_df["cluster_label"].value_counts().reset_index()
            pie_data.columns = ["Segment", "Count"]
            fig_pie = px.pie(
                pie_data, names="Segment", values="Count",
                title="Customer Segment Distribution", hole=0.35,
            )
            fig_pie.update_layout(height=380)
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        x_col = "recency_days" if "recency_days" in seg_df.columns else None
        y_col = "monetary"     if "monetary"     in seg_df.columns else None
        c_col = "cluster_label" if "cluster_label" in seg_df.columns else None
        if x_col and y_col:
            fig_sc = px.scatter(
                seg_df, x=x_col, y=y_col, color=c_col,
                title="Monetary Value vs Recency",
                labels={x_col: "Recency (days)", y_col: "Monetary Value"},
                opacity=0.65,
            )
            fig_sc.update_layout(height=380)
            st.plotly_chart(fig_sc, use_container_width=True)
