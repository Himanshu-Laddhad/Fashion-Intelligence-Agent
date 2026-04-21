import io
import sys
import logging
import warnings
import numpy as np
import pandas as pd
from prophet import Prophet

warnings.filterwarnings("ignore")
for _name in ("prophet", "cmdstanpy"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.ERROR)
    _log.handlers.clear()
    _log.propagate = False


def prepare_prophet_df(timeseries_df: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    Convert a pytrends interest-over-time DataFrame to Prophet format.

    Prophet requires columns named 'ds' (datetime) and 'y' (numeric).
    timeseries_df is expected to have a DatetimeIndex and either a column
    named after the query or simply a first numeric column.
    """
    if timeseries_df is None or timeseries_df.empty:
        return pd.DataFrame()

    df = timeseries_df.copy()

    # Reset DatetimeIndex to a plain column
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={"index": "ds", "date": "ds"})
    elif "ds" not in df.columns:
        df = df.reset_index()

    # Pick the value column: prefer query-named column, else first numeric
    if query in df.columns:
        value_col = query
    else:
        numeric_cols = [
            c for c in df.columns
            if c not in ("ds", "date", "isPartial")
            and pd.api.types.is_numeric_dtype(df[c])
        ]
        if not numeric_cols:
            return pd.DataFrame()
        value_col = numeric_cols[0]

    # Ensure ds column exists
    date_col = "ds" if "ds" in df.columns else "date"
    out = pd.DataFrame({
        "ds": pd.to_datetime(df[date_col]),
        "y":  pd.to_numeric(df[value_col], errors="coerce"),
    }).dropna()

    return out.reset_index(drop=True)


def fit_and_forecast(prophet_df: pd.DataFrame, periods: int = 90) -> dict:
    """
    Fit a Prophet model on prophet_df and forecast `periods` days ahead.

    Returns a result dict with availability flag, direction, and forecast records.
    """
    if prophet_df is None or prophet_df.empty or len(prophet_df) < 10:
        return {"available": False, "reason": "insufficient data"}

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
    )

    # Suppress Prophet / cmdstanpy stdout and logging during fit
    _stdout = sys.stdout
    sys.stdout = io.StringIO()
    logging.disable(logging.INFO)
    try:
        model.fit(prophet_df)
    finally:
        logging.disable(logging.NOTSET)
        sys.stdout = _stdout

    future   = model.make_future_dataframe(periods=periods, freq="D")
    forecast = model.predict(future)

    # Future-only rows
    cutoff        = prophet_df["ds"].max()
    future_fc     = forecast[forecast["ds"] > cutoff].copy()

    # Trend direction: last-30 vs first-30 of the future forecast
    yhat = future_fc["yhat"].values
    if len(yhat) >= 30:
        first30 = float(np.mean(yhat[:30]))
        last30  = float(np.mean(yhat[-30:]))
    else:
        first30 = float(np.mean(yhat[:len(yhat) // 2])) if len(yhat) > 1 else float(np.mean(yhat))
        last30  = float(np.mean(yhat[len(yhat) // 2:])) if len(yhat) > 1 else first30

    delta = last30 - first30
    if delta > 5:
        direction = "rising"
    elif delta < -5:
        direction = "falling"
    else:
        direction = "stable"

    tail30 = future_fc[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(30).copy()
    tail30["ds"] = tail30["ds"].dt.strftime("%Y-%m-%d")

    return {
        "available":        True,
        "forecast_periods": periods,
        "trend_direction":  direction,
        "forecast":         tail30.to_dict("records"),
        "changepoints":     len(model.changepoints),
    }


def forecast_trend(query: str, timeseries_df: pd.DataFrame) -> dict:
    """Entry point: prepare → fit → forecast. Returns safe dict on any error."""
    try:
        prophet_df = prepare_prophet_df(timeseries_df, query)
        return fit_and_forecast(prophet_df)
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


if __name__ == "__main__":
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="W")
    vals  = np.random.randint(20, 80, len(dates)).astype(float)
    df    = pd.DataFrame({"ds": dates, "y": vals})

    result = fit_and_forecast(df, periods=90)
    print("Forecast available:", result.get("available"))
    print("Direction:", result.get("trend_direction"))
    print("Forecaster OK")
