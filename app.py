"""Fashion Intelligence — Trend Explorer."""

import asyncio
import math
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import db
from backend.ai_analyzer import generate_dashboard_copy, verify_and_caption_images
from backend.fashion_scorer import score_and_rank_images
from data_sources.google_trends import compute_trend_momentum
from scrapers.pinterest_scraper import scrape_pinterest_optimized


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Fashion Trend Explorer",
    page_icon="📊",
    layout="wide",
)


# ── Constants ─────────────────────────────────────────────────────────────────

ALL_OPTION = "Any"

CLASS_OPTIONS = [
    ALL_OPTION, "jacket", "coat", "blazer", "shirt", "top",
    "dress", "skirt", "pants", "hoodie", "sweater", "set", "shoes",
]
COLOUR_OPTIONS = [
    ALL_OPTION, "black", "white", "beige", "brown", "blue",
    "navy", "grey", "green", "red", "pink", "silver",
]
OCCASION_OPTIONS = [
    ALL_OPTION, "everyday", "office", "weekend", "party",
    "date night", "travel", "formal", "casual", "workout",
]
MATERIAL_OPTIONS = [
    ALL_OPTION, "denim", "cotton", "linen", "silk", "wool",
    "leather", "knit", "satin", "nylon", "cashmere",
]
STYLE_OPTIONS = [
    ALL_OPTION, "minimal", "streetwear", "quiet luxury", "romantic",
    "tailored", "sporty", "utility", "preppy", "edgy", "boho",
]
TIMEFRAME_OPTIONS = {
    "Past 12 months": "today 12-m",
    "Past 5 years":   "today 5-y",
    "Past 90 days":   "today 3-m",
    "Past 30 days":   "today 1-m",
}
MAX_IMAGES = 12


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug or "trend"


def _clean_choice(value: str) -> str:
    return value if value and value != ALL_OPTION else ""


def _build_search_phrase(filters: dict) -> str:
    parts = []
    if filters.get("colour"):
        parts.append(filters["colour"])
    if filters.get("material"):
        parts.append(filters["material"])
    if filters.get("class"):
        parts.append(filters["class"])
    if filters.get("occasion"):
        parts.append(f"for {filters['occasion']}")
    if filters.get("style"):
        parts.append(filters["style"])
    if filters.get("extra"):
        parts.append(filters["extra"])
    return " ".join(p for p in parts if p).strip() or "fashion trends"


def _run_async(coro):
    """Run async coroutine safely in Streamlit context."""
    try:
        loop = asyncio.get_running_loop()
        # Already in event loop - create new one in executor thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


def _fetch_interest_over_time(query: str, timeframe: str) -> pd.DataFrame:
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([query], cat=0, timeframe=timeframe, geo="", gprop="")
        return pt.interest_over_time()
    except (ConnectionError, ValueError, KeyError, Exception) as exc:
        st.warning(f"⚠️ pytrends error: {exc}")
        return pd.DataFrame()


def _fetch_region_interest(query: str, timeframe: str) -> pd.DataFrame:
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([query], cat=0, timeframe=timeframe, geo="", gprop="")
        return pt.interest_by_region(resolution="COUNTRY", inc_low_vol=False).reset_index()
    except (ConnectionError, ValueError, KeyError, Exception) as exc:
        st.warning(f"⚠️ pytrends region error: {exc}")
        return pd.DataFrame()


def _fetch_related_queries(query: str) -> dict:
    from pytrends.request import TrendReq
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([query], cat=0, timeframe="today 12-m", geo="", gprop="")
        return pt.related_queries()
    except (ConnectionError, ValueError, KeyError, Exception) as exc:
        st.warning(f"⚠️ pytrends related query error: {exc}")
        return {}


def _build_momentum_table(ts_df: pd.DataFrame, query: str) -> pd.DataFrame:
    if ts_df is None or ts_df.empty or query not in ts_df.columns:
        return pd.DataFrame([{
            "Keyword": query,
            "Direction": "Unknown",
            "Momentum": 0.0,
            "Recent Avg (0–100)": 0.0,
            "Historical Avg (0–100)": 0.0,
        }])
    stats = compute_trend_momentum(ts_df[[query]])
    return pd.DataFrame([{
        "Keyword": query,
        "Direction": stats["direction"].capitalize(),
        "Momentum": round(stats["momentum"], 3),
        "Recent Avg (0–100)": round(stats["recent_avg"], 1),
        "Historical Avg (0–100)": round(stats["historical_avg"], 1),
    }])


def _collect_trend_terms(related_queries: dict, query: str, limit: int = 10) -> pd.DataFrame:
    if not related_queries:
        return pd.DataFrame(columns=["Rank", "Trend", "Value"])
    
    bucket = related_queries.get(query)
    if bucket is None:
        bucket = next(iter(related_queries.values()), None)
    
    if not bucket or not isinstance(bucket, dict):
        return pd.DataFrame(columns=["Rank", "Trend", "Value"])

    rows = []
    for source in ("top", "rising"):
        df = bucket.get(source)
        if df is None or df.empty:
            continue
        term_col = next(
            (c for c in df.columns if c.lower() in {"query", "term", "topic", "keyword"}),
            df.columns[0],
        )
        value_col = next(
            (c for c in df.columns if c.lower() in {"value", "score", "traffic"}),
            None,
        )
        for _, row in df.head(limit).iterrows():
            term = str(row.get(term_col, "")).strip()
            if not term or term.lower() == query.lower():
                continue
            rows.append({"Trend": term, "Value": row.get(value_col) if value_col else None})

    if not rows:
        return pd.DataFrame(columns=["Rank", "Trend", "Value"])

    trend_df = pd.DataFrame(rows)
    trend_df["_lower"] = trend_df["Trend"].str.lower()
    trend_df = trend_df.drop_duplicates(subset=["_lower"]).drop(columns=["_lower"]).head(limit)
    trend_df.insert(0, "Rank", range(1, len(trend_df) + 1))
    return trend_df


def _build_trend_bubble_figure(trend_terms_df: pd.DataFrame) -> go.Figure | None:
    """Build a compact monochromatic packed-bubble chart for trend terms."""
    if trend_terms_df is None or trend_terms_df.empty:
        return None

    bubble_df = trend_terms_df.copy()
    bubble_df["score"] = pd.to_numeric(bubble_df.get("Value"), errors="coerce")

    # If Google returns non-numeric values (e.g. "Breakout"), keep a usable visual ranking.
    if bubble_df["score"].isna().all():
        bubble_df["score"] = [max(10, (len(bubble_df) - i) * 10) for i in range(len(bubble_df))]
    else:
        bubble_df["score"] = bubble_df["score"].fillna(bubble_df["score"].median())

    bubble_df = bubble_df.sort_values("score", ascending=False).reset_index(drop=True)
    if bubble_df.empty:
        return None

    min_score = float(bubble_df["score"].min())
    max_score = float(bubble_df["score"].max())
    score_span = max(max_score - min_score, 1.0)

    def _norm(v: float) -> float:
        return (float(v) - min_score) / score_span

    def _bubble_label(term: str, score: float) -> str:
        text = str(term).strip()
        if len(text) > 20:
            text = text[:17] + "..."
        words = text.split()
        if len(words) >= 2 and len(text) > 11:
            split_at = len(words) // 2
            text = " ".join(words[:split_at]) + "<br>" + " ".join(words[split_at:])
        return f"{text}<br><b>{int(round(score))}</b>"

    bubbles = []
    for idx, row in bubble_df.iterrows():
        score = float(row["score"])
        n = _norm(score)
        radius = 0.26 + (n ** 0.65) * 0.34

        if idx == 0:
            x, y = 0.0, 0.0
        else:
            angle = idx * 2.3999632297
            seed_radius = 0.12 * idx
            x = seed_radius * math.cos(angle)
            y = seed_radius * math.sin(angle)

        bubbles.append(
            {
                "trend": str(row["Trend"]),
                "score": score,
                "norm": n,
                "r": radius,
                "x": x,
                "y": y,
            }
        )

    # Tight circle packing with center gravity for a compact cluster.
    for _ in range(220):
        moved = False
        for i in range(len(bubbles)):
            for j in range(i + 1, len(bubbles)):
                bi = bubbles[i]
                bj = bubbles[j]
                dx = bj["x"] - bi["x"]
                dy = bj["y"] - bi["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 1e-6
                min_dist = bi["r"] + bj["r"] + 0.012
                if dist < min_dist:
                    overlap = min_dist - dist
                    ux = dx / dist
                    uy = dy / dist
                    shift = overlap * 0.52
                    bi["x"] -= ux * shift
                    bi["y"] -= uy * shift
                    bj["x"] += ux * shift
                    bj["y"] += uy * shift
                    moved = True

        for b in bubbles:
            b["x"] *= 0.986
            b["y"] *= 0.986

        if not moved:
            break

    fig_bubbles = go.Figure()

    for b in bubbles:
        # Monochromatic palette: one hue (blue), varied lightness by score.
        lightness = 30 + b["norm"] * 38
        fill = f"hsl(212, 72%, {lightness:.1f}%)"

        fig_bubbles.add_shape(
            type="circle",
            xref="x",
            yref="y",
            x0=b["x"] - b["r"],
            y0=b["y"] - b["r"],
            x1=b["x"] + b["r"],
            y1=b["y"] + b["r"],
            line=dict(color="rgba(188,210,255,0.55)", width=1.5),
            fillcolor=fill,
            opacity=0.93,
        )
        fig_bubbles.add_annotation(
            x=b["x"],
            y=b["y"],
            text=_bubble_label(b["trend"], b["score"]),
            showarrow=False,
            align="center",
            font=dict(color="white", size=10 + int(b["norm"] * 5)),
        )

    fig_bubbles.add_trace(
        go.Scatter(
            x=[b["x"] for b in bubbles],
            y=[b["y"] for b in bubbles],
            mode="markers",
            marker=dict(size=2, color="rgba(0,0,0,0)"),
            customdata=[(b["trend"], b["score"]) for b in bubbles],
            hovertemplate="<b>%{customdata[0]}</b><br>Score: %{customdata[1]:.0f}<extra></extra>",
            showlegend=False,
        )
    )

    extent = max(max(abs(b["x"]) + b["r"], abs(b["y"]) + b["r"]) for b in bubbles) + 0.08
    fig_bubbles.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=8, b=8),
        xaxis=dict(visible=False, range=[-extent, extent]),
        yaxis=dict(visible=False, range=[-extent, extent]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_bubbles.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig_bubbles


async def _scrape_and_verify(
    search_phrase: str,
    trend_terms: list[str],
    trend_term_scores: dict[str, float],
) -> list[dict]:
    """Scrape Pinterest images and verify with LLM."""
    queries = [search_phrase]
    for term in trend_terms:
        if term and term.lower() != search_phrase.lower() and term not in queries:
            queries.append(term)
        if len(queries) >= 3:
            break

    collected, seen_urls = [], set()
    tmp_dir = Path("outputs") / "tmp_scrape"

    for index, term in enumerate(queries):
        per_query_limit = MAX_IMAGES if index == 0 else max(3, MAX_IMAGES // 3)
        query_dir = tmp_dir / _slugify(term)
        query_dir.mkdir(parents=True, exist_ok=True)
        df = await scrape_pinterest_optimized(term, query_dir, max_images=per_query_limit)
        if df is None or df.empty or "image_url" not in df.columns:
            continue
        for _, row in df.iterrows():
            url = row.get("image_url")
            if not url or not isinstance(url, str) or url in seen_urls:
                continue
            seen_urls.add(url)
            collected.append({
                "url": url,
                "description": row.get("description", term),
            })
            if len(collected) >= MAX_IMAGES:
                break

    urls = [img["url"] for img in collected]
    verified = await verify_and_caption_images(urls, search_phrase, limit=MAX_IMAGES)
    ranked = await score_and_rank_images(
        images=verified,
        search_phrase=search_phrase,
        trend_terms=trend_terms,
        trend_term_scores=trend_term_scores,
        top_k=6,
    )
    return ranked


def _render_verified_grid(verified_images: list) -> None:
    """Render verified image grid."""
    shown = [img for img in (verified_images or []) if img.get("url")]
    if not shown:
        st.info("No relevant images found for this filter combination.")
        return

    verified_count = sum(1 for img in shown if img.get("verified"))
    label = (
        f"{len(shown)} images · {verified_count} verified by Groq Vision"
        if verified_count
        else f"{len(shown)} trend-aligned images from Pinterest"
    )
    st.caption(label)

    for start in range(0, len(shown), 2):
        cols = st.columns(2, gap="medium")
        for col_idx, col in enumerate(cols):
            img_idx = start + col_idx
            if img_idx >= len(shown):
                continue
            with col:
                st.image(shown[img_idx]["url"], use_container_width=True)
                caption = shown[img_idx].get("caption")
                if caption:
                    st.caption(caption)
                score = shown[img_idx].get("fashion_score")
                if score is not None:
                    st.caption(f"Fashion Score: {float(score):.1f}/100")


# ── Validation tab ────────────────────────────────────────────────────────────

def _render_validation_tab() -> None:
    RESULTS_DIR = Path("backtest/results")
    metrics_path = RESULTS_DIR / "metrics.csv"
    summary_path = RESULTS_DIR / "summary.txt"
    spaghetti_path = RESULTS_DIR / "spaghetti_chart.png"
    lead_time_path = RESULTS_DIR / "lead_time_chart.png"

    if not metrics_path.exists():
        st.info("No backtest results found. Run `python -m backtest.run_backtest` first.")
        return

    metrics_df = pd.read_csv(metrics_path)
    metrics_df["confirmed"] = metrics_df["confirmed"].astype(bool)
    metrics_df["data_available"] = metrics_df["data_available"].astype(bool)

    available = metrics_df[metrics_df["data_available"]]
    tp = int(available["tp"].sum())
    tn = int(available["tn"].sum())
    fp = int(available["fp"].sum())
    fn = int(available["fn"].sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    accuracy  = (tp + tn) / len(available) if len(available) > 0 else 0

    early = available[available["scorer_flagged_rising"] & available["lead_weeks"].notna() & (available["lead_weeks"] >= 0)]
    avg_lead    = early["lead_weeks"].mean() if not early.empty else 0
    median_lead = early["lead_weeks"].median() if not early.empty else 0

    st.subheader("Momentum Signal — Pinterest Predicts Backtest")
    st.caption(
        f"Validated against {len(available)} fashion trend queries from Pinterest Predicts "
        f"2024–2026 · ground truth: Pinterest retrospective labels"
    )

    st.markdown("#### Classification metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Precision", f"{precision:.2f}", help="Of trends flagged rising, how many were confirmed")
    m2.metric("Recall",    f"{recall:.2f}",    help="Of confirmed rising trends, how many were flagged")
    m3.metric("F1",        f"{f1:.2f}")
    m4.metric("Accuracy",  f"{accuracy:.2f}")

    st.markdown("#### Lead time — confirmed rising trends")
    l1, l2, l3 = st.columns(3)
    l1.metric("Mean lead time",   f"{avg_lead:.1f} weeks",    help="Weeks before actual peak the scorer first flagged 'rising'")
    l2.metric("Median lead time", f"{median_lead:.1f} weeks")
    l3.metric("Flagged before peak", f"{len(early)} / {int(available['confirmed'].sum())} confirmed")

    st.markdown("#### Confusion matrix")
    cm_col, _ = st.columns([1, 2])
    with cm_col:
        st.dataframe(
            pd.DataFrame(
                {"Predicted Rising": [tp, fp], "Predicted Not Rising": [fn, tn]},
                index=["Actually Rising", "Actually Not Rising"],
            ),
            use_container_width=True,
        )

    st.divider()
    st.markdown("#### Momentum score over time — confirmed rising trends (2024–2025)")
    if spaghetti_path.exists():
        st.image(str(spaghetti_path), use_container_width=True)
        st.caption("Each line = one confirmed rising trend · dashed line = rising threshold (0.1) · x-axis = weeks relative to peak")
    else:
        st.info("Spaghetti chart not found — run the visualize step.")

    st.markdown("#### Lead time by query")
    if lead_time_path.exists():
        st.image(str(lead_time_path), use_container_width=True)
        st.caption("Bar length = weeks before actual interest peak the scorer first flagged 'rising'")
    else:
        st.info("Lead time chart not found — run the visualize step.")

    st.divider()
    st.markdown("#### Per-query results")
    display_cols = ["query", "predicted_year", "confirmed", "scorer_flagged_rising", "peak_date", "first_rising_date", "lead_weeks"]
    display_cols = [c for c in display_cols if c in metrics_df.columns]
    st.dataframe(
        metrics_df[display_cols].sort_values(["predicted_year", "confirmed"], ascending=[True, False]),
        use_container_width=True,
        hide_index=True,
    )

    if summary_path.exists():
        with st.expander("Raw summary output"):
            st.code(summary_path.read_text(encoding="utf-8", errors="replace"))


# ── Session state ─────────────────────────────────────────────────────────────

if "trend_refresh_nonce" not in st.session_state:
    st.session_state["trend_refresh_nonce"] = 0

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📊 Fashion Trend Explorer")
st.caption("Live Google Trends · trend-aligned images · LLM-normalized dashboard copy.")


# ── Filter controls ───────────────────────────────────────────────────────────

with st.expander("⚙️ Trend Filters", expanded=True):
    fc1, fc2, fc3 = st.columns(3)
    fd1, fd2, fd3 = st.columns(3)

    with fc1:
        class_choice = st.selectbox("Class", CLASS_OPTIONS, index=1)
    with fc2:
        colour_choice = st.selectbox("Colour", COLOUR_OPTIONS, index=0)
    with fc3:
        occasion_choice = st.selectbox("Occasion", OCCASION_OPTIONS, index=0)
    with fd1:
        material_choice = st.selectbox("Material", MATERIAL_OPTIONS, index=0)
    with fd2:
        style_choice = st.selectbox("Style", STYLE_OPTIONS, index=0)
    with fd3:
        timeframe_label = st.selectbox("Trend window", list(TIMEFRAME_OPTIONS.keys()), index=0)

    extra_choice = st.text_input("Other detail", placeholder="e.g. oversized, relaxed fit, cropped")

    if st.button("🔄 Refresh Trends", use_container_width=True):
        db.clear()
        st.session_state["trend_refresh_nonce"] += 1
        st.rerun()

    st.caption("Refresh wipes cached data and fetches everything fresh.")

timeframe = TIMEFRAME_OPTIONS[timeframe_label]
filters = {
    "class":    _clean_choice(class_choice),
    "colour":   _clean_choice(colour_choice),
    "occasion": _clean_choice(occasion_choice),
    "material": _clean_choice(material_choice),
    "style":    _clean_choice(style_choice),
    "extra":    extra_choice.strip(),
}
search_phrase = _build_search_phrase(filters)

st.markdown(f"**Search phrase:** {search_phrase}")

tab_explorer, tab_validation = st.tabs(["📈 Trend Explorer", "📊 Signal Validation"])

with tab_validation:
    _render_validation_tab()

with tab_explorer:

    # ── Fetch or load trend data ──────────────────────────────────────────────

    if db.has_trend(search_phrase, timeframe):
        ts_df, region_df, trend_terms_df = db.load_trend(search_phrase, timeframe)
        trend_terms = trend_terms_df["Trend"].tolist() if not trend_terms_df.empty else []
        trend_term_scores = (
            {
                str(row["Trend"]): float(row["Value"])
                for _, row in trend_terms_df.iterrows()
                if row.get("Trend") and row.get("Value") is not None and not pd.isna(row.get("Value"))
            }
            if trend_terms_df is not None and not trend_terms_df.empty
            else {}
        )
    else:
        with st.spinner(f"Fetching live trends for '{search_phrase}'…"):
            ts_df          = _fetch_interest_over_time(search_phrase, timeframe)
            region_df      = _fetch_region_interest(search_phrase, timeframe)
            related        = _fetch_related_queries(search_phrase)
            trend_terms_df = _collect_trend_terms(related, search_phrase, limit=10)
            trend_terms    = trend_terms_df["Trend"].tolist() if not trend_terms_df.empty else []
            trend_term_scores = (
                {
                    str(row["Trend"]): float(row["Value"])
                    for _, row in trend_terms_df.iterrows()
                    if row.get("Trend") and row.get("Value") is not None and not pd.isna(row.get("Value"))
                }
                if trend_terms_df is not None and not trend_terms_df.empty
                else {}
            )
            db.save_trend(search_phrase, timeframe, ts_df, region_df, trend_terms_df)

    _copy_key = f"{search_phrase}:{st.session_state['trend_refresh_nonce']}"
    if st.session_state.get("_copy_cache_key") != _copy_key:
        st.session_state["dashboard_copy"] = _run_async(
            generate_dashboard_copy(filters=filters, search_phrase=search_phrase, trend_terms=trend_terms)
        )
        st.session_state["_copy_cache_key"] = _copy_key
    dashboard_copy = st.session_state["dashboard_copy"]

    copy_col, metric_col = st.columns([3, 1])
    with copy_col:
        st.subheader(dashboard_copy.get("headline", "Live fashion trends"))
        st.markdown(dashboard_copy.get("summary", "Live fashion trend data is ready."))
        if dashboard_copy.get("microcopy"):
            st.caption(dashboard_copy["microcopy"])
        if dashboard_copy.get("normalized_phrase"):
            st.caption(f"Normalized phrase: {dashboard_copy['normalized_phrase']}")

    st.divider()

    # ── 1. Interest Over Time ─────────────────────────────────────────────────

    st.subheader("📈 Interest Over Time")

    col_interest, col_bubbles = st.columns([3, 2], gap="large")

    with col_interest:
        if ts_df is not None and not ts_df.empty and search_phrase in ts_df.columns:
            plot_df = ts_df.drop(columns=["isPartial"], errors="ignore").reset_index()
            x_col = next((c for c in plot_df.columns if c != search_phrase), plot_df.columns[0])
            plot_df = plot_df.rename(columns={search_phrase: "Interest"})
            fig = px.line(
                plot_df, x=x_col, y="Interest",
                title=f"Google Trends Interest — {timeframe_label}",
                labels={x_col: "Date", "Interest": "Interest (0–100)"},
            )
            fig.update_layout(yaxis_range=[0, 100], height=430, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "No trend data returned. Google Trends may be rate-limiting. "
                "Press **🔄 Refresh Trends** to try again."
            )

    with col_bubbles:
        st.markdown("**Trend Bubbles**")
        st.caption("Monochrome packed view · bubble size = score")
        fig_bubbles_inline = _build_trend_bubble_figure(trend_terms_df)
        if fig_bubbles_inline is not None:
            st.plotly_chart(fig_bubbles_inline, use_container_width=True)
        else:
            st.info("No related trend terms available for bubble view.")

    st.divider()

    # ── 2. Momentum Scorecard ─────────────────────────────────────────────────

    st.subheader("🚀 Trend Momentum")

    mom_df = _build_momentum_table(ts_df, search_phrase)
    if not mom_df.empty:
        raw_momentum    = float(mom_df.iloc[0]["Momentum"])
        direction_label = str(mom_df.iloc[0]["Direction"])
        recent          = float(mom_df.iloc[0]["Recent Avg (0–100)"])
        historical      = float(mom_df.iloc[0]["Historical Avg (0–100)"])

        _dir_cfg = {
            "Rising":  ("#2ecc71", "🟢 Rising"),
            "Falling": ("#e74c3c", "🔴 Falling"),
            "Stable":  ("#f39c12", "🟡 Stable"),
        }
        bar_color, direction_display = _dir_cfg.get(direction_label, ("#95a5a6", "⚪ Unknown"))

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=raw_momentum,
            number={"valueformat": ".3f", "font": {"size": 56, "color": bar_color}},
            title={
                "text": "Momentum Score<br><span style='font-size:13px;color:#888'>−1 falling · 0 stable · +1 rising</span>",
                "font": {"size": 15},
            },
            gauge={
                "axis": {
                    "range": [-1, 1],
                    "tickvals": [-1, -0.5, 0, 0.5, 1],
                    "ticktext": ["−1", "−0.5", "0", "+0.5", "+1"],
                    "tickfont": {"color": "#aaa"},
                },
                "bar": {"color": bar_color, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [-1.0, -0.1], "color": "rgba(231,76,60,0.12)"},
                    {"range": [-0.1,  0.1], "color": "rgba(241,196,15,0.10)"},
                    {"range": [ 0.1,  1.0], "color": "rgba(46,204,113,0.12)"},
                ],
                "threshold": {"line": {"color": bar_color, "width": 3}, "thickness": 0.8, "value": raw_momentum},
            },
        ))
        fig_gauge.update_layout(
            height=280, margin=dict(l=30, r=30, t=50, b=10),
            paper_bgcolor="rgba(0,0,0,0)", font_color="white",
        )

        col_gauge, col_stats = st.columns([2, 1])
        with col_gauge:
            st.plotly_chart(fig_gauge, use_container_width=True)
        with col_stats:
            st.metric("Direction", direction_display)
            st.metric("Recent Interest (8-week avg)", f"{recent:.1f} / 100")
            st.metric("Historical Baseline", f"{historical:.1f} / 100",
                      delta=f"{recent - historical:+.1f} vs baseline")

        if direction_label == "Rising":
            insight = (
                f"**{search_phrase.title()}** is gaining momentum. "
                f"Recent interest ({recent:.0f}/100) is {recent - historical:.0f} pts above the "
                f"historical baseline ({historical:.0f}/100) — a strengthening trend."
            )
        elif direction_label == "Falling":
            insight = (
                f"**{search_phrase.title()}** is losing steam. "
                f"Recent interest ({recent:.0f}/100) dropped {historical - recent:.0f} pts below "
                f"the historical baseline ({historical:.0f}/100). May be past peak."
            )
        else:
            insight = (
                f"**{search_phrase.title()}** is holding steady. "
                f"Recent interest ({recent:.0f}/100) is close to the historical baseline "
                f"({historical:.0f}/100) — no strong directional signal."
            )
        st.markdown(insight)
    else:
        st.info("Momentum data unavailable — trend fetch required first.")

    st.divider()

    # ── 3. Geographic Interest ────────────────────────────────────────────────

    st.subheader("🌍 Geographic Interest")

    if region_df is not None and not region_df.empty:
        region_df.columns = [c.lower() for c in region_df.columns]
        value_col = next((c for c in region_df.columns if c != "geoname"), None)

        if value_col:
            active = region_df[region_df[value_col] > 0].copy()
            freq = dict(zip(active["geoname"], active[value_col].astype(float)))

            if freq:
                from wordcloud import WordCloud
                import matplotlib.pyplot as plt

                col_globe, col_wc = st.columns(2, gap="medium")

                with col_globe:
                    fig_globe = go.Figure(data=go.Choropleth(
                        locations=active["geoname"],
                        z=active[value_col].astype(float),
                        locationmode="country names",
                        colorscale=[
                            [0.0, "rgba(50, 10, 80, 0.3)"],
                            [0.4, "rgba(120, 40, 160, 0.7)"],
                            [1.0, "#c39bd3"],
                        ],
                        marker_line_color="rgba(180,180,220,0.25)",
                        marker_line_width=0.5,
                        colorbar=dict(
                            title=dict(text="Interest", font=dict(color="#ccc")),
                            thickness=10, len=0.55,
                            tickfont=dict(color="#ccc"),
                            bgcolor="rgba(0,0,0,0)", borderwidth=0,
                        ),
                        zmin=0, zmax=100,
                    ))
                    fig_globe.update_geos(
                        projection_type="orthographic",
                        showocean=True, oceancolor="rgb(12, 12, 28)",
                        showland=True, landcolor="rgb(30, 30, 50)",
                        showframe=False, showcountries=True,
                        countrycolor="rgba(140, 140, 180, 0.35)",
                        showcoastlines=True,
                        coastlinecolor="rgba(140, 140, 180, 0.35)",
                        bgcolor="rgba(0,0,0,0)",
                        lataxis_showgrid=False, lonaxis_showgrid=False,
                    )
                    fig_globe.update_layout(
                        title=dict(
                            text=f"<b>{search_phrase}</b> — {timeframe_label}",
                            font=dict(color="#ddd", size=13), x=0.5,
                        ),
                        geo=dict(bgcolor="rgba(0,0,0,0)"),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        height=420, margin=dict(l=0, r=0, t=36, b=0),
                        font_color="white", dragmode="orbit",
                    )
                    st.plotly_chart(fig_globe, use_container_width=True)
                    st.caption("Drag to rotate · Scroll to zoom")

                with col_wc:
                    wc = WordCloud(
                        width=700, height=420,
                        background_color=None,
                        mode="RGBA",
                        colormap="cool",
                        max_words=50,
                        prefer_horizontal=0.80,
                        min_font_size=11,
                        max_font_size=120,
                        collocations=False,
                    ).generate_from_frequencies(freq)

                    fig_wc, ax = plt.subplots(figsize=(7, 4.2))
                    fig_wc.patch.set_alpha(0)
                    ax.set_facecolor("none")
                    ax.imshow(wc, interpolation="bilinear")
                    ax.axis("off")
                    st.pyplot(fig_wc, use_container_width=True)
                    plt.close(fig_wc)
                    st.caption(f"Word size = search interest · {len(freq)} countries")
    else:
        st.info("No regional data available for this filter combination.")

    st.divider()

    # ── 5. Trend-Aligned Images ───────────────────────────────────────────────

    st.subheader("🖼️ Trend-Aligned Images")

    if db.has_images(search_phrase):
        verified_images = db.load_images(search_phrase)
    else:
        with st.spinner("Fetching and verifying trend-aligned images…"):
            verified_images = _run_async(
                _scrape_and_verify(search_phrase, trend_terms, trend_term_scores)
            )
        db.save_images(search_phrase, verified_images)

    _render_verified_grid(verified_images)

    st.divider()
