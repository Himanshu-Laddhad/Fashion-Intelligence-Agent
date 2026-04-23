# Fashion Intelligence — Pytrends Decoupling Tasks
> Goal: Make pytrends the **primary, standalone** intelligence layer.  
> Scrapers become optional. The dashboard works with ZERO scraper calls.  
>
> Give Cursor **one task at a time**. Run **Verify** before moving on.

---

## WHY THIS CHANGE
The scrapers (Firecrawl, Selenium, Crawl4AI) are fragile — they break on API key expiry,
rate limits, DOM changes, and bot detection. pytrends is free, stable, and returns 
real consumer demand data from Google. This refactor makes the core app reliable.

---

## TASK P1 — Rebuild the pytrends Module as a Full Intelligence Layer

**Prerequisites:** `data_sources/google_trends.py` already exists (replace it entirely)  
**Touches:** `data_sources/google_trends.py` — full replacement, same filename  

**Cursor Prompt:**
```
Replace the entire contents of data_sources/google_trends.py with the following implementation.
Do not keep any of the old code — rewrite the file from scratch.

IMPORTS:
import time
import random
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from pytrends.request import TrendReq

---

CONSTANTS:
FASHION_CATEGORY = 185        # Google Trends: Shopping > Apparel & Accessories
DEFAULT_TIMEFRAMES = {
    "1y":  "today 12-m",
    "5y":  "today 5-y",
    "90d": "today 3-m",
    "1m":  "today 1-m",
}
MAX_RETRIES = 3
RETRY_BASE_SLEEP = 5   # seconds

---

FUNCTION: _make_pytrends() -> TrendReq:
    Returns TrendReq(hl="en-US", tz=360, retries=2, backoff_factor=0.5)

FUNCTION: _sleep_politely():
    Sleeps random.uniform(2.0, 4.0) seconds (polite rate-limit avoidance)

FUNCTION: _safe_fetch(fn, label: str, default):
    Wraps fn() in try/except with up to MAX_RETRIES attempts.
    On each failure: print warning with label, sleep RETRY_BASE_SLEEP * attempt, continue.
    Returns fn() result on first success, or default if all retries fail.

---

FUNCTION: fetch_interest_over_time(
        queries: List[str],
        timeframe: str = "today 5-y",
        geo: str = "",
        category: int = FASHION_CATEGORY) -> pd.DataFrame:
    - Validates: queries must be 1–5 items (pytrends limit). Truncate silently if > 5.
    - Builds payload then calls interest_over_time()
    - Drops the "isPartial" column if present
    - Calls _sleep_politely() after fetch
    - Returns DataFrame with DatetimeIndex and one column per query term
    - Returns empty DataFrame on any failure

FUNCTION: fetch_interest_by_region(
        query: str,
        resolution: str = "COUNTRY",
        timeframe: str = "today 12-m") -> pd.DataFrame:
    - Fetches interest_by_region(resolution=resolution, inc_low_vol=True, inc_geo_code=False)
    - Returns DataFrame with columns: [query, geoName] (reset index)
    - Returns empty DataFrame on failure

FUNCTION: fetch_related_queries(query: str, timeframe: str = "today 5-y") -> Dict:
    - Returns related_queries() dict for the single query
    - Safely extracts: result[query]["top"] and result[query]["rising"] as DataFrames
    - Returns {"top": DataFrame or None, "rising": DataFrame or None}
    - Returns {"top": None, "rising": None} on failure

FUNCTION: fetch_related_topics(query: str) -> Dict:
    - Returns related_topics() dict
    - Safely extracts: result[query]["top"] and result[query]["rising"]
    - Returns {"top": DataFrame or None, "rising": DataFrame or None}
    - Returns {"top": None, "rising": None} on failure

FUNCTION: fetch_trending_searches(geo: str = "united_states") -> pd.DataFrame:
    - Calls trending_searches(pn=geo)
    - Returns the DataFrame (single column of trending terms)
    - Returns empty DataFrame on failure

FUNCTION: compare_terms(
        terms: List[str],
        timeframe: str = "today 5-y") -> pd.DataFrame:
    - Calls fetch_interest_over_time(terms, timeframe)
    - Returns the raw interest DataFrame (terms as columns, dates as index)
    - This is used for multi-term trend comparison charts

---

FUNCTION: compute_momentum(series: pd.Series) -> Dict[str, Any]:
    - series: a single named pandas Series of interest values (0–100 scale)
    - recent_avg = mean of last 8 data points
    - historical_avg = mean of points from index -52 to -8 (or earlier half if < 52)
    - raw_momentum = (recent_avg - historical_avg) / (historical_avg + 1e-9)
    - momentum = clip(raw_momentum, -1, 1)
    - direction = "rising" if momentum > 0.10 else "falling" if momentum < -0.10 else "stable"
    - acceleration = mean of last 4 points minus mean of points -8 to -4 (rate of change of recent trend)
    - Returns: {"momentum": float, "direction": str, "recent_avg": float,
                "historical_avg": float, "acceleration": float,
                "peak_value": float, "current_value": float}

FUNCTION: compute_seasonality(series: pd.Series) -> Dict[str, Any]:
    - Needs at least 104 weekly data points (2 years) to detect seasonality
    - If insufficient data: return {"seasonal": False}
    - Groups by month (series.index.month) and computes mean per month
    - peak_month = month with highest mean, trough_month = lowest mean
    - seasonal_amplitude = (peak_mean - trough_mean) / (overall_mean + 1e-9)
    - Returns: {"seasonal": True, "peak_month": int, "trough_month": int,
                "amplitude": float, "monthly_profile": dict (month -> mean)}

---

FUNCTION: get_full_trend_profile(
        query: str,
        timeframe: str = "today 5-y") -> Dict[str, Any]:
    """
    Master function: returns everything about a single search term.
    This is the main entry point for the dashboard.
    """
    profile = {"query": query, "timeframe": timeframe, "available": False}

    # 1. Interest over time
    ts_df = fetch_interest_over_time([query], timeframe=timeframe)
    if ts_df.empty or query not in ts_df.columns:
        profile["error"] = "No data returned from Google Trends"
        return profile

    profile["available"] = True
    profile["timeseries"] = ts_df                            # full DataFrame
    series = ts_df[query].astype(float)

    # 2. Momentum
    profile["momentum"] = compute_momentum(series)

    # 3. Seasonality
    profile["seasonality"] = compute_seasonality(series)

    # 4. Related queries (with _sleep_politely between calls)
    _sleep_politely()
    profile["related_queries"] = fetch_related_queries(query, timeframe)

    # 5. Geographic breakdown
    _sleep_politely()
    profile["geo_breakdown"] = fetch_interest_by_region(query)

    return profile

FUNCTION: get_comparison_profile(
        terms: List[str],
        timeframe: str = "today 5-y") -> Dict[str, Any]:
    """
    Returns comparison data for multiple terms side-by-side.
    """
    terms = terms[:5]   # pytrends hard limit
    ts_df = fetch_interest_over_time(terms, timeframe=timeframe)
    if ts_df.empty:
        return {"available": False, "terms": terms}

    summaries = {}
    for term in terms:
        if term in ts_df.columns:
            summaries[term] = compute_momentum(ts_df[term].astype(float))

    return {
        "available": True,
        "terms": terms,
        "timeseries": ts_df,
        "summaries": summaries,
    }

---

if __name__ == "__main__":
    print("Testing pytrends module...")
    profile = get_full_trend_profile("denim jacket", timeframe="today 12-m")
    print("Available:", profile["available"])
    if profile["available"]:
        print("Direction:", profile["momentum"]["direction"])
        print("Momentum:", round(profile["momentum"]["momentum"], 3))
        print("Timeseries rows:", len(profile["timeseries"]))
    print("pytrends module OK")
```

**Verify:**
```bash
python data_sources/google_trends.py
```
✅ Pass = prints direction, momentum value, timeseries row count, "pytrends module OK"  
(If rate-limited, "Available: False" is still a pass — no crash is what matters)

---

## TASK P2 — Create a Standalone Pytrends Flask API (No Scrapers)

**Prerequisites:** Task P1  
**Creates:** `routes/trends_routes.py`, `routes/__init__.py`  
**Touches:** `server.py` — registers the new blueprint  

**Cursor Prompt:**
```
Create routes/__init__.py as an empty file.

Create routes/trends_routes.py.

This is a Flask Blueprint that exposes pytrends data via REST endpoints.
It has NO dependency on any scraper. It imports ONLY from data_sources/google_trends.py.

IMPORTS:
from flask import Blueprint, request, jsonify
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from data_sources.google_trends import (
    get_full_trend_profile, get_comparison_profile,
    fetch_trending_searches, fetch_interest_by_region,
    fetch_related_queries
)
import pandas as pd

trends_bp = Blueprint("trends", __name__, url_prefix="/api/trends")

---

ENDPOINT 1: GET /api/trends/profile?q=<term>&timeframe=<tf>
@trends_bp.route("/profile", methods=["GET"])
def trend_profile():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    timeframe = request.args.get("timeframe", "today 5-y")
    profile = get_full_trend_profile(q, timeframe=timeframe)
    
    # Serialise DataFrames to JSON-safe format
    result = {
        "query": profile["query"],
        "available": profile["available"],
        "error": profile.get("error"),
    }
    if profile["available"]:
        ts = profile["timeseries"]
        result["timeseries"] = {
            "dates": ts.index.strftime("%Y-%m-%d").tolist(),
            "values": ts[q].tolist() if q in ts.columns else [],
        }
        result["momentum"] = profile["momentum"]
        result["seasonality"] = profile.get("seasonality", {})
        
        rq = profile.get("related_queries", {})
        result["related_queries"] = {
            "top": rq["top"].head(10).to_dict("records") if rq.get("top") is not None else [],
            "rising": rq["rising"].head(10).to_dict("records") if rq.get("rising") is not None else [],
        }
        geo = profile.get("geo_breakdown", pd.DataFrame())
        result["geo_breakdown"] = geo.head(20).to_dict("records") if not geo.empty else []
    
    return jsonify(result)

---

ENDPOINT 2: GET /api/trends/compare?terms=<t1,t2,t3>&timeframe=<tf>
@trends_bp.route("/compare", methods=["GET"])
def trend_compare():
    raw = request.args.get("terms", "")
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    if len(terms) < 2:
        return jsonify({"error": "At least 2 comma-separated terms required"}), 400
    timeframe = request.args.get("timeframe", "today 5-y")
    comp = get_comparison_profile(terms, timeframe=timeframe)
    
    result = {"available": comp["available"], "terms": comp["terms"]}
    if comp["available"]:
        ts = comp["timeseries"]
        result["timeseries"] = {
            "dates": ts.index.strftime("%Y-%m-%d").tolist(),
        }
        for term in comp["terms"]:
            if term in ts.columns:
                result["timeseries"][term] = ts[term].tolist()
        result["summaries"] = comp["summaries"]
    return jsonify(result)

---

ENDPOINT 3: GET /api/trends/trending?geo=united_states
@trends_bp.route("/trending", methods=["GET"])
def trending_now():
    geo = request.args.get("geo", "united_states")
    df = fetch_trending_searches(geo=geo)
    terms = df.iloc[:, 0].tolist() if not df.empty else []
    return jsonify({"geo": geo, "trending": terms[:20]})

---

ENDPOINT 4: GET /api/trends/related?q=<term>
@trends_bp.route("/related", methods=["GET"])
def related_queries():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    rq = fetch_related_queries(q)
    return jsonify({
        "query": q,
        "top": rq["top"].head(10).to_dict("records") if rq.get("top") is not None else [],
        "rising": rq["rising"].head(10).to_dict("records") if rq.get("rising") is not None else [],
    })

---

Now modify server.py:
1. After the existing imports, add:
   from routes.trends_routes import trends_bp
2. After `app = Flask(__name__)` and `CORS(app)`, add:
   app.register_blueprint(trends_bp)
3. In the startup print block, add these lines to the API endpoints list:
   print("   GET  /api/trends/profile  - Full trend profile (pytrends only)")
   print("   GET  /api/trends/compare  - Multi-term comparison")
   print("   GET  /api/trends/trending - Trending searches now")
   print("   GET  /api/trends/related  - Related queries")

Do not change anything else in server.py.
```

**Verify:**
```bash
python -c "
from routes.trends_routes import trends_bp
from flask import Flask
app = Flask(__name__)
app.register_blueprint(trends_bp)
rules = [str(r) for r in app.url_map.iter_rules()]
assert any('trends' in r for r in rules), 'trends routes not registered'
print('Routes registered:', [r for r in rules if 'trends' in r])
print('Trends routes OK')
"
```
✅ Pass = prints the 4 /api/trends/* routes, "Trends routes OK"

---

## TASK P3 — Make Scrapers Fully Optional in the Orchestrator

**Prerequisites:** Task P1  
**Touches:** `backend/orchestrator.py` — wrap scraper calls in isolation  

**Cursor Prompt:**
```
Modify backend/orchestrator.py. Goal: if ALL scrapers fail, the app still returns 
a useful result using pytrends data. No scraper failure should crash the pipeline.

Make ONLY these changes (do not touch anything else):

1. Find the asyncio.gather() block (around line 54-65). 
   It currently looks like:
       pinterest_task = scrape_pinterest_optimized(...)
       zara_task = scrape_zara(...)
       ...
       pinterest_df, zara_df, uniqlo_df, vogue_df = await asyncio.gather(...)

   Replace the ENTIRE try/except block around asyncio.gather 
   (from "try:" through the last "vogue_df = pd.DataFrame()") with:

   # ── Scrapers (all optional — failures are isolated) ──────────────────
   async def _safe_scrape(coro, name: str) -> pd.DataFrame:
       try:
           result = await coro
           if isinstance(result, Exception):
               print(f"   ⚠️  {name} returned exception: {result}")
               return pd.DataFrame()
           print(f"   ✅ {name}: {len(result)} rows")
           return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
       except Exception as exc:
           print(f"   ⚠️  {name} scraper failed: {exc}")
           return pd.DataFrame()

   pinterest_df, zara_df, uniqlo_df, vogue_df = await asyncio.gather(
       _safe_scrape(scrape_pinterest_optimized(query, output_dir, max_images=12), "Pinterest"),
       _safe_scrape(scrape_zara(query, output_dir), "Zara"),
       _safe_scrape(scrape_uniqlo(query, output_dir), "Uniqlo"),
       _safe_scrape(scrape_vogue(query, output_dir), "Vogue"),
   )

2. After the data collection summary print block, add:
   scraper_total = len(pinterest_df) + len(zara_df) + len(uniqlo_df) + len(vogue_df)
   scrapers_available = scraper_total > 0
   if not scrapers_available:
       print("   ℹ️  All scrapers returned empty — running in pytrends-only mode")

3. In the final result dict, add:
   "scrapers_available": scrapers_available,
   "scraper_total_items": scraper_total,

Do not change anything else. The rest of the pipeline runs identically regardless 
of scraper success.
```

**Verify:**
```bash
python -c "
import ast, pathlib
src = pathlib.Path('backend/orchestrator.py').read_text()
assert '_safe_scrape' in src, '_safe_scrape function not found'
assert 'scrapers_available' in src, 'scrapers_available flag not added'
print('Orchestrator decoupling OK')
"
```
✅ Pass = prints "Orchestrator decoupling OK"

---

## TASK P4 — Update app.py to Display Pytrends Data When Scrapers Fail

**Prerequisites:** Task P3  
**Touches:** `app.py` — add a pytrends-first display block  

**Cursor Prompt:**
```
Modify app.py. Add a "Pytrends Intelligence" section that ALWAYS shows, 
whether or not scrapers succeeded. Insert it BEFORE the existing display_moodboards() call.

1. In the display_results() function, find the line:
       # Display moodboards
       display_moodboards(result, message_index)
   
   BEFORE that line, insert this entire block:
   
   # ── Pytrends Intelligence Section ─────────────────────────────
   tvi = result.get("tvi", {})
   google_signal = result.get("google_signal", {})
   
   if tvi or google_signal:
       st.markdown("---")
       st.markdown("### 📈 Trend Intelligence (Google Trends)")
       
       # TVI Score card row
       c1, c2, c3, c4 = st.columns(4)
       tvi_score = tvi.get("tvi", 0)
       confidence = tvi.get("confidence", "—")
       direction = google_signal.get("direction", "unknown")
       momentum = google_signal.get("momentum", 0)
       
       direction_emoji = {"rising": "🟢 Rising", "falling": "🔴 Falling", "stable": "🟡 Stable"}.get(direction, "⚪ Unknown")
       
       with c1:
           st.metric("Trend Velocity Index", f"{tvi_score:.1f} / 100", help="Composite score: Google momentum + retail presence")
       with c2:
           st.metric("Signal Confidence", confidence.title())
       with c3:
           st.metric("Direction", direction_emoji)
       with c4:
           st.metric("Momentum", f"{momentum:+.2f}", help="Positive = accelerating, negative = decelerating")
       
       # Rising related queries
       related = google_signal.get("related_queries", {})
       rising_df = related.get(result.get("query",""), {}).get("rising") if isinstance(related.get(result.get("query","")), dict) else None
       
       # Try flat structure too (the module returns it differently)
       if rising_df is None and isinstance(related, dict):
           for key in related:
               val = related[key]
               if isinstance(val, dict) and "rising" in val:
                   df_val = val["rising"]
                   if df_val is not None and not (hasattr(df_val, 'empty') and df_val.empty):
                       rising_df = df_val
                       break
       
       if rising_df is not None and hasattr(rising_df, 'empty') and not rising_df.empty:
           st.markdown("**🔥 Rising Related Searches:**")
           if "query" in rising_df.columns:
               pills = " ".join([f'<span class="trend-pill">{q}</span>' for q in rising_df["query"].head(8).tolist()])
               st.markdown(pills, unsafe_allow_html=True)
       
       # Scraper status notice
       if not result.get("scrapers_available", True):
           st.info("ℹ️ Product scrapers unavailable — trend intelligence is powered by Google Trends data only.")

2. Do not change any other function or existing logic.
```

**Verify:**
```bash
python -c "
import ast, pathlib
src = pathlib.Path('app.py').read_text()
assert 'Trend Intelligence' in src, 'TVI section not added'
assert 'scrapers_available' in src, 'scraper status notice not added'
print('app.py update OK')
"
```
✅ Pass = prints "app.py update OK"

---

## TASK P5 — Build the Standalone Pytrends Dashboard (No Flask, No Scrapers)

**Prerequisites:** Task P1  
**Creates:** `pages/trend_explorer.py`  
**Touches:** Nothing existing  

**Cursor Prompt:**
```
Create pages/trend_explorer.py.

This is a completely standalone Streamlit page. 
It calls pytrends DIRECTLY — no Flask server, no scrapers, no DuckDB needed.
It works even if the Flask backend is offline.

IMPORTS:
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_sources.google_trends import (
    get_full_trend_profile, get_comparison_profile,
    fetch_trending_searches, fetch_interest_over_time,
    fetch_related_queries, compute_momentum
)

---

PAGE CONFIG:
st.set_page_config(
    page_title="Trend Explorer", page_icon="📈", layout="wide"
)

---

SIDEBAR:
st.sidebar.title("⚙️ Trend Explorer Settings")
mode = st.sidebar.radio(
    "Mode",
    ["🔍 Single Term Deep Dive", "⚖️ Compare Terms", "🌍 Trending Now"],
    key="mode"
)
timeframe_label = st.sidebar.selectbox(
    "Time Range",
    ["Last Month", "Last 3 Months", "Last 12 Months", "Last 5 Years"],
    index=3
)
TIMEFRAME_MAP = {
    "Last Month": "today 1-m",
    "Last 3 Months": "today 3-m",
    "Last 12 Months": "today 12-m",
    "Last 5 Years": "today 5-y",
}
timeframe = TIMEFRAME_MAP[timeframe_label]

---

MAIN HEADER:
st.title("📈 Fashion Trend Explorer")
st.caption("Powered by Google Trends — no scrapers required")

---

SECTION A — "🔍 Single Term Deep Dive" mode:

Show:
  query_input = st.text_input("Fashion term to explore:", placeholder="e.g. barrel jeans, mob wife aesthetic, quiet luxury")
  search_btn = st.button("Analyse Trend", type="primary")
  
  If search_btn and query_input:
      with st.spinner(f"Fetching Google Trends data for '{query_input}'..."):
          profile = get_full_trend_profile(query_input, timeframe=timeframe)
      
      if not profile["available"]:
          st.error(f"Could not fetch data: {profile.get('error', 'Unknown error')}. Google Trends may be rate-limiting — wait 60 seconds and retry.")
          st.stop()
      
      momentum = profile["momentum"]
      
      # ── Row 1: KPI metrics ────────────────────────────────────────
      m1, m2, m3, m4, m5 = st.columns(5)
      direction_map = {"rising": ("🟢 Rising", "normal"), "falling": ("🔴 Falling", "inverse"), "stable": ("🟡 Stable", "off")}
      dir_label, dir_delta_color = direction_map.get(momentum["direction"], ("⚪ Unknown", "off"))
      
      m1.metric("Direction", dir_label)
      m2.metric("Current Interest", f"{momentum['current_value']:.0f} / 100")
      m3.metric("Recent Avg (8wk)", f"{momentum['recent_avg']:.1f}")
      m4.metric("Historical Avg", f"{momentum['historical_avg']:.1f}")
      m5.metric("Momentum Score", f"{momentum['momentum']:+.2f}")
      
      # ── Row 2: Interest over time chart ──────────────────────────
      st.markdown("#### 📊 Interest Over Time")
      ts = profile["timeseries"]
      fig = px.area(
          ts.reset_index(),
          x=ts.index.name or "date",
          y=query_input,
          title=f'Google Search Interest: "{query_input}"',
          labels={"x": "Date", query_input: "Interest (0–100)"},
          color_discrete_sequence=["#667eea"],
      )
      fig.update_layout(showlegend=False, height=350,
                        margin=dict(l=0, r=0, t=40, b=0))
      st.plotly_chart(fig, use_container_width=True)
      
      # ── Row 3: Seasonality + Geographic split ─────────────────────
      col_left, col_right = st.columns(2)
      
      with col_left:
          st.markdown("#### 🌍 Geographic Interest")
          geo_df = profile.get("geo_breakdown", pd.DataFrame())
          if not geo_df.empty and query_input in geo_df.columns:
              geo_df = geo_df.sort_values(query_input, ascending=False).head(15)
              fig_geo = px.bar(
                  geo_df, x=query_input, y="geoName",
                  orientation="h",
                  title="Top Regions by Search Interest",
                  color=query_input, color_continuous_scale="Purples",
                  labels={query_input: "Interest", "geoName": ""},
              )
              fig_geo.update_layout(height=400, showlegend=False,
                                    margin=dict(l=0, r=0, t=40, b=0),
                                    coloraxis_showscale=False)
              st.plotly_chart(fig_geo, use_container_width=True)
          else:
              st.info("Geographic data unavailable")
      
      with col_right:
          st.markdown("#### 🔥 Rising Related Searches")
          rq = profile.get("related_queries", {})
          rising = rq.get("rising")
          top = rq.get("top")
          
          if rising is not None and not rising.empty and "query" in rising.columns:
              st.markdown("**Rising now:**")
              for _, row in rising.head(10).iterrows():
                  val = row.get("value", "")
                  val_str = "Breakout" if val == 0 else f"+{val}%"
                  st.markdown(f"- **{row['query']}** `{val_str}`")
          elif top is not None and not top.empty and "query" in top.columns:
              st.markdown("**Top searches:**")
              for _, row in top.head(10).iterrows():
                  st.markdown(f"- {row['query']} ({row.get('value', '')})")
          else:
              st.info("Related queries unavailable")
      
      # ── Row 4: Seasonality ────────────────────────────────────────
      seasonality = profile.get("seasonality", {})
      if seasonality.get("seasonal"):
          st.markdown("#### 🗓️ Seasonal Pattern")
          month_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                         7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
          mp = seasonality.get("monthly_profile", {})
          if mp:
              months = list(mp.keys())
              values = list(mp.values())
              month_labels = [month_names.get(m, str(m)) for m in months]
              fig_season = px.bar(
                  x=month_labels, y=values,
                  title=f"Average Monthly Interest (seasonal amplitude: {seasonality['amplitude']:.1%})",
                  labels={"x": "Month", "y": "Avg Interest"},
                  color=values, color_continuous_scale="Purples",
              )
              fig_season.update_layout(height=280, showlegend=False,
                                       coloraxis_showscale=False,
                                       margin=dict(l=0, r=0, t=40, b=0))
              st.plotly_chart(fig_season, use_container_width=True)
              peak_m = month_names.get(seasonality["peak_month"])
              trough_m = month_names.get(seasonality["trough_month"])
              st.caption(f"📅 Peak month: **{peak_m}** | Trough: **{trough_m}**")
      else:
          if seasonality:  # has data but not seasonal
              st.caption("No significant seasonal pattern detected.")

---

SECTION B — "⚖️ Compare Terms" mode:

Show:
  st.markdown("Enter up to 5 comma-separated fashion terms to compare their Google search volume.")
  terms_input = st.text_input("Terms to compare:", placeholder="e.g. skinny jeans, wide leg jeans, barrel jeans")
  compare_btn = st.button("Compare", type="primary")
  
  If compare_btn and terms_input:
      terms = [t.strip() for t in terms_input.split(",") if t.strip()][:5]
      if len(terms) < 2:
          st.warning("Enter at least 2 terms separated by commas.")
      else:
          with st.spinner(f"Comparing {len(terms)} terms..."):
              comp = get_comparison_profile(terms, timeframe=timeframe)
          
          if not comp["available"]:
              st.error("Could not fetch comparison data. Try again in 60 seconds.")
          else:
              ts = comp["timeseries"]
              
              # Line chart comparison
              st.markdown("#### 📊 Relative Search Interest Over Time")
              fig = px.line(
                  ts.reset_index(),
                  x=ts.index.name or "date",
                  y=terms,
                  title="Search Interest Comparison (Google Trends)",
                  labels={"value": "Interest (0–100)", "variable": "Term"},
              )
              fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
              st.plotly_chart(fig, use_container_width=True)
              
              # Summary table
              st.markdown("#### 📋 Momentum Summary")
              rows = []
              for term, summary in comp["summaries"].items():
                  dir_emoji = {"rising": "🟢", "falling": "🔴", "stable": "🟡"}.get(summary["direction"], "⚪")
                  rows.append({
                      "Term": term,
                      "Direction": f"{dir_emoji} {summary['direction'].title()}",
                      "Current Interest": f"{summary['current_value']:.0f}",
                      "8-wk Avg": f"{summary['recent_avg']:.1f}",
                      "Momentum": f"{summary['momentum']:+.2f}",
                  })
              st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

---

SECTION C — "🌍 Trending Now" mode:

Show:
  geo_options = {
      "United States": "united_states",
      "United Kingdom": "united_kingdom",
      "Australia": "australia",
      "India": "india",
      "Canada": "canada",
  }
  geo_label = st.selectbox("Region:", list(geo_options.keys()))
  
  st.info("Shows what's trending RIGHT NOW on Google in this region (not filtered to fashion).")
  
  refresh_btn = st.button("🔄 Fetch Trending Now", type="primary")
  if refresh_btn:
      with st.spinner("Fetching trending searches..."):
          df = fetch_trending_searches(geo=geo_options[geo_label])
      
      if df.empty:
          st.warning("Could not fetch trending data — rate limited. Try again in 60 seconds.")
      else:
          terms = df.iloc[:, 0].tolist()[:25]
          st.markdown(f"#### 🔥 Trending Now in {geo_label}")
          cols = st.columns(5)
          for i, term in enumerate(terms):
              with cols[i % 5]:
                  st.markdown(f"`{i+1}.` {term}")

---

FOOTER:
st.markdown("---")
st.caption("Data source: Google Trends via pytrends. Refreshes on each button click. Rate limit: ~1 request per 5 seconds.")
```

**Verify:**
```bash
python -c "
import ast, pathlib
src = pathlib.Path('pages/trend_explorer.py').read_text()
ast.parse(src)   # syntax check
assert 'get_full_trend_profile' in src
assert 'get_comparison_profile' in src
assert 'fetch_trending_searches' in src
print('Trend Explorer syntax OK')
"
```
✅ Pass = prints "Trend Explorer syntax OK" (no SyntaxError)

---

## TASK P6 — Add Rate-Limit Retry Cache to pytrends Module

**Prerequisites:** Task P1 already complete  
**Creates:** `data_sources/trends_cache.py`  
**Touches:** `data_sources/google_trends.py` — add caching import  

This prevents the dashboard from hammering Google Trends and getting blocked mid-session.

**Cursor Prompt:**
```
Create data_sources/trends_cache.py.

This module provides an in-memory + file-based cache for pytrends responses.
It prevents duplicate API calls within the same session and across short sessions.

IMPORTS: json, hashlib, pathlib, datetime, pandas, pickle

CACHE_DIR = pathlib.Path("outputs/.trends_cache")

FUNCTION: _cache_key(query: str, fn_name: str, timeframe: str) -> str:
    Combined = f"{fn_name}::{query}::{timeframe}"
    Returns hashlib.md5(combined.encode()).hexdigest()[:12]

FUNCTION: _cache_path(key: str) -> pathlib.Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    Returns CACHE_DIR / f"{key}.pkl"

FUNCTION: cache_get(query: str, fn_name: str, timeframe: str, ttl_minutes: int = 60):
    key = _cache_key(query, fn_name, timeframe)
    path = _cache_path(key)
    if not path.exists():
        return None
    age_minutes = (datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)).seconds / 60
    if age_minutes > ttl_minutes:
        path.unlink(missing_ok=True)
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None

FUNCTION: cache_set(query: str, fn_name: str, timeframe: str, data) -> None:
    key = _cache_key(query, fn_name, timeframe)
    path = _cache_path(key)
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as exc:
        print(f"Cache write failed: {exc}")

FUNCTION: cache_clear_old(max_age_hours: int = 24) -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=max_age_hours)
    for p in CACHE_DIR.glob("*.pkl"):
        if datetime.datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
            p.unlink()
            count += 1
    return count

---

Now modify data_sources/google_trends.py:

1. Add this import at the very top (after existing imports):
   from data_sources.trends_cache import cache_get, cache_set

2. In the get_full_trend_profile() function, at the very start (before "profile = {...}"):
   # Check cache first
   cached = cache_get(query, "full_profile", timeframe, ttl_minutes=60)
   if cached is not None:
       print(f"   ✅ Cache hit for '{query}' ({timeframe})")
       return cached

3. At the very end of get_full_trend_profile(), just before the final `return profile`:
   cache_set(query, "full_profile", timeframe, profile)

4. In get_comparison_profile(), at the start (before "terms = terms[:5]"):
   terms_key = ",".join(sorted(terms[:5]))
   cached = cache_get(terms_key, "comparison", timeframe, ttl_minutes=60)
   if cached is not None:
       print(f"   ✅ Cache hit for comparison '{terms_key}'")
       return cached

5. At the end of get_comparison_profile(), just before `return {...}`:
   result = {"available": True, "terms": terms, "timeseries": ts_df, "summaries": summaries}
   cache_set(terms_key, "comparison", timeframe, result)
   return result

Do not change anything else.
```

**Verify:**
```bash
python -c "
from data_sources.trends_cache import cache_get, cache_set, cache_clear_old
import pandas as pd
cache_set('test', 'test_fn', 'today 5-y', {'value': 42})
result = cache_get('test', 'test_fn', 'today 5-y', ttl_minutes=60)
assert result == {'value': 42}, f'Expected dict, got {result}'
print('Cache hit:', result)
n = cache_clear_old(max_age_hours=0)
print('Cleared', n, 'old cache files')
print('Cache module OK')
"
```
✅ Pass = prints "Cache hit: {'value': 42}", "Cache module OK"

---

## TASK P7 — Update the Existing Analytics Dashboard to Show Trend Scores

**Prerequisites:** Tasks P1, P5  
**Touches:** `pages/analytics_dashboard.py` — add a live TVI section from DuckDB  

**Cursor Prompt:**
```
Modify pages/analytics_dashboard.py.

Find the "TREND VELOCITY INDEX HISTORY" section (section 2 in the file).
Replace only that section with the following improved version:

st.markdown("---")
st.subheader("📈 Trend Velocity Index — Query History")

try:
    tvi_df = _safe_read(
        "SELECT query, scored_at, tvi_score, google_trend_score, retail_score, confidence "
        "FROM trend_scores ORDER BY scored_at DESC LIMIT 200",
        "TVI history"
    )
    
    if tvi_df is None or tvi_df.empty:
        st.info("No TVI data yet. Run a query in the main app first.")
    else:
        tvi_df["scored_at"] = pd.to_datetime(tvi_df["scored_at"])
        
        # KPI row
        latest = tvi_df.iloc[0]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Latest TVI", f"{latest['tvi_score']:.1f} / 100")
        k2.metric("Confidence", str(latest["confidence"]).title())
        k3.metric("Unique Queries Tracked", tvi_df["query"].nunique())
        k4.metric("Total Analysis Runs", len(tvi_df))
        
        # Time series chart — one line per query
        st.markdown("**TVI Score Over Time by Query**")
        fig = px.line(
            tvi_df,
            x="scored_at",
            y="tvi_score",
            color="query",
            markers=True,
            labels={"scored_at": "Date", "tvi_score": "TVI Score", "query": "Query"},
            height=350,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        # Component breakdown for latest query
        st.markdown("**Component Scores (Latest Run)**")
        comp_data = {
            "Component": ["Google Trends", "Retail Presence"],
            "Score": [latest["google_trend_score"], latest["retail_score"]],
        }
        fig2 = px.bar(
            comp_data, x="Component", y="Score",
            color="Component", color_discrete_sequence=["#667eea", "#764ba2"],
            range_y=[0, 100], height=250,
        )
        fig2.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig2, use_container_width=True)

except Exception as e:
    st.warning(f"Could not load TVI data: {e}")

Do not change any other section of the file.
```

**Verify:**
```bash
python -c "
import ast, pathlib
src = pathlib.Path('pages/analytics_dashboard.py').read_text()
ast.parse(src)
assert 'Component Scores' in src
print('Analytics dashboard update OK')
"
```
✅ Pass = prints "Analytics dashboard update OK"

---

## FINAL SMOKE TEST — All Pytrends Tasks

Run after ALL P-tasks are complete:

```bash
python -c "
# 1. Core module
from data_sources.google_trends import (
    get_full_trend_profile, get_comparison_profile,
    fetch_trending_searches, compute_momentum
)

# 2. Cache
from data_sources.trends_cache import cache_get, cache_set

# 3. Routes
from routes.trends_routes import trends_bp

# 4. Orchestrator still imports cleanly
from backend.orchestrator import run_fashion_query

# 5. Pages parse cleanly
import ast, pathlib
for page in ['pages/trend_explorer.py', 'pages/analytics_dashboard.py']:
    ast.parse(pathlib.Path(page).read_text())
    print(f'  {page} — syntax OK')

print()
print('ALL PYTRENDS TASKS VERIFIED ✅')
print()
print('To run the standalone Trend Explorer:')
print('  streamlit run pages/trend_explorer.py')
print()
print('To run the full app (scrapers optional):')
print('  python server.py      # terminal 1')
print('  streamlit run app.py  # terminal 2')
"
```

✅ All imports succeed, both pages parse cleanly.

---

## WHAT YOU NOW HAVE

```
Before these tasks:           After these tasks:
─────────────────────         ─────────────────────────────────────
App breaks if scrapers fail   App works with ZERO scraper calls
No caching — every run        60-min cache — instant repeat queries
  re-hits Google Trends         avoids rate limits between sessions
TVI shown only in backend     TVI shown prominently in UI
One page Streamlit app        Multi-page: Main App + Trend Explorer
                                          + Analytics Dashboard
No trend comparison UI        Full multi-term comparison with charts
No geo breakdown              Geographic interest by country
No seasonal analysis          Monthly interest profile + peak/trough
No related query display      Rising + top related queries shown
Flask required for all data   Trend Explorer works standalone
                               (no Flask needed at all)
```

## HOW TO USE THE STANDALONE TREND EXPLORER

No Flask server needed. Just:
```bash
streamlit run pages/trend_explorer.py
```

Open http://localhost:8501 and search any fashion term directly.
Results cache for 60 minutes so re-runs are instant.
