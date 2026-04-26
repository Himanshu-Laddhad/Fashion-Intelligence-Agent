import time
import pandas as pd
from typing import Dict, Any
from pytrends.request import TrendReq


def fetch_trend_timeseries(query: str, timeframe: str = "today 5-y") -> pd.DataFrame:
    """Fetch Google Trends interest-over-time for a single query. Returns empty DataFrame on error."""
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([query], cat=0, timeframe=timeframe, geo="", gprop="")
        time.sleep(2)
        return pt.interest_over_time()
    except Exception as exc:
        print(f"⚠️  pytrends warning for '{query}': {exc}")
        return pd.DataFrame()


def fetch_related_queries(query: str) -> dict:
    """Fetch Google Trends related queries for a single query. Returns empty dict on error."""
    try:
        pt = TrendReq(hl="en-US", tz=360)
        pt.build_payload([query], cat=0, timeframe="today 5-y", geo="", gprop="")
        return pt.related_queries()
    except Exception as exc:
        print(f"⚠️  pytrends related_queries warning for '{query}': {exc}")
        return {}


def compute_trend_momentum(timeseries_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Derive momentum from a pytrends interest-over-time DataFrame.

    Returns a dict with:
        momentum        float  clipped to [-1, 1]
        direction       str    'rising' | 'falling' | 'stable'
        recent_avg      float  mean of last 8 weeks
        historical_avg  float  mean of weeks 52-9 from the end
    """
    if timeseries_df.empty:
        return {
            "momentum": 0.0,
            "direction": "unknown",
            "recent_avg": 0.0,
            "historical_avg": 0.0,
        }

    # Use the first non-isPartial numeric column
    numeric_cols = [
        c for c in timeseries_df.columns
        if c != "isPartial" and pd.api.types.is_numeric_dtype(timeseries_df[c])
    ]
    if not numeric_cols:
        return {
            "momentum": 0.0,
            "direction": "unknown",
            "recent_avg": 0.0,
            "historical_avg": 0.0,
        }

    series = timeseries_df[numeric_cols[0]].astype(float)

    recent_avg = float(series.iloc[-8:].mean()) if len(series) >= 8 else float(series.mean())

    if len(series) >= 52:
        historical_slice = series.iloc[-(52):-8]
    elif len(series) > 8:
        historical_slice = series.iloc[:-8]
    else:
        historical_slice = series

    historical_avg = float(historical_slice.mean()) if not historical_slice.empty else 0.0

    raw_momentum = (recent_avg - historical_avg) / (historical_avg + 1e-9)
    momentum = float(max(-1.0, min(1.0, raw_momentum)))

    if momentum > 0.1:
        direction = "rising"
    elif momentum < -0.1:
        direction = "falling"
    else:
        direction = "stable"

    return {
        "momentum": momentum,
        "direction": direction,
        "recent_avg": recent_avg,
        "historical_avg": historical_avg,
    }


def get_trend_signal(query: str) -> Dict[str, Any]:
    """
    Full pipeline: fetch timeseries → compute momentum → fetch related queries.

    Returns merged dict with keys:
        momentum, direction, recent_avg, historical_avg, related_queries, query
    """
    timeseries_df = fetch_trend_timeseries(query)
    momentum_result = compute_trend_momentum(timeseries_df)
    related = fetch_related_queries(query)

    return {
        **momentum_result,
        "related_queries": related,
        "query": query,
    }


if __name__ == "__main__":
    result = get_trend_signal("denim jacket")
    print(result)
