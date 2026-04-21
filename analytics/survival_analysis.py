import warnings
import numpy as np
import pandas as pd
from datetime import timedelta
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import multivariate_logrank_test

warnings.filterwarnings("ignore")


def prepare_survival_df(
    transactions_df: pd.DataFrame,
    customers_df: pd.DataFrame = None,
    churn_threshold_days: float = 120.0,
) -> pd.DataFrame:
    """
    Build a customer-level survival DataFrame from raw transactions.

    duration       = (last_purchase - first_purchase).days + 1
    event_observed = True when the customer has been inactive longer than
                     churn_threshold_days relative to the global observation end.
    """
    df = transactions_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    agg = (
        df.groupby("customer_id")["transaction_date"]
        .agg(first_purchase="min", last_purchase="max")
        .reset_index()
    )

    observation_end = agg["last_purchase"].max() + timedelta(days=1)

    agg["duration"] = (agg["last_purchase"] - agg["first_purchase"]).dt.days + 1
    agg["days_inactive"] = (observation_end - agg["last_purchase"]).dt.days
    agg["event_observed"] = agg["days_inactive"] > churn_threshold_days

    # Enforce minimum duration of 1
    agg["duration"] = agg["duration"].clip(lower=1)

    survival_df = agg[["customer_id", "duration", "event_observed",
                        "first_purchase", "last_purchase"]].copy()

    if customers_df is not None and not customers_df.empty:
        keep = [c for c in ["customer_id", "age", "club_member_status"]
                if c in customers_df.columns]
        survival_df = survival_df.merge(
            customers_df[keep], on="customer_id", how="left"
        )
        if "age" in survival_df.columns:
            median_age = survival_df["age"].median()
            survival_df["age"] = survival_df["age"].fillna(median_age)

    return survival_df


def fit_kaplan_meier(
    survival_df: pd.DataFrame,
    group_col: str = None,
) -> dict:
    """
    Fit Kaplan-Meier survival curves, optionally stratified by group_col.

    Returns overall curve, per-group curves, and log-rank p-value.
    """
    durations = survival_df["duration"]
    events    = survival_df["event_observed"]

    # Overall curve
    kmf = KaplanMeierFitter()
    kmf.fit(durations, event_observed=events, label="overall")
    sf = kmf.survival_function_

    overall = {
        "timeline":        sf.index.tolist(),
        "survival_prob":   sf.iloc[:, 0].tolist(),
        "median_survival": float(kmf.median_survival_time_),
    }

    by_group     = {}
    logrank_pval = None

    if group_col and group_col in survival_df.columns:
        groups = survival_df[group_col].dropna().unique()
        group_durations = []
        group_events    = []

        for g in sorted(groups, key=str):
            mask = survival_df[group_col] == g
            d, e = durations[mask], events[mask]
            group_durations.append(d)
            group_events.append(e)

            kmf_g = KaplanMeierFitter()
            kmf_g.fit(d, event_observed=e, label=str(g))
            sf_g  = kmf_g.survival_function_
            by_group[str(g)] = {
                "timeline":      sf_g.index.tolist(),
                "survival_prob": sf_g.iloc[:, 0].tolist(),
            }

        if len(groups) >= 2:
            group_labels = np.concatenate([
                np.full(len(d), str(g))
                for g, d in zip(sorted(groups, key=str), group_durations)
            ])
            all_dur = pd.concat(group_durations).reset_index(drop=True)
            all_evt = pd.concat(group_events).reset_index(drop=True)
            try:
                lr = multivariate_logrank_test(all_dur, group_labels,
                                               event_observed=all_evt)
                logrank_pval = float(lr.p_value)
            except Exception:
                logrank_pval = None

    return {
        "overall":          overall,
        "by_group":         by_group,
        "log_rank_p_value": logrank_pval,
        # convenience shortcut used by callers
        "median_survival":  overall["median_survival"],
    }


def fit_cox_ph(
    survival_df: pd.DataFrame,
    covariate_cols: list,
) -> dict:
    """
    Fit a penalised Cox Proportional Hazards model.

    Returns hazard ratios, p-values, concordance index, and HTML summary.
    """
    _empty = {
        "hazard_ratios":          {},
        "p_values":               {},
        "concordance":            0.0,
        "significant_covariates": [],
        "summary_html":           "",
    }

    available_covars = [c for c in covariate_cols if c in survival_df.columns]
    if not available_covars:
        return _empty

    cols_needed = ["duration", "event_observed"] + available_covars
    df_fit = survival_df[cols_needed].dropna()

    if len(df_fit) < 20:
        return _empty

    # Drop constant covariates (Cox can't handle them)
    varying = [c for c in available_covars if df_fit[c].nunique() > 1]
    if not varying:
        return _empty

    df_fit = df_fit[["duration", "event_observed"] + varying]

    try:
        cph = CoxPHFitter(penalizer=0.1)
        cph.fit(df_fit, duration_col="duration", event_col="event_observed")

        summary    = cph.summary
        hr         = cph.hazard_ratios_.to_dict()
        p_vals     = summary["p"].to_dict()
        concordance = float(cph.concordance_index_)
        sig_covars  = [c for c, p in p_vals.items() if p < 0.05]

        return {
            "hazard_ratios":          {k: float(v) for k, v in hr.items()},
            "p_values":               {k: float(v) for k, v in p_vals.items()},
            "concordance":            concordance,
            "significant_covariates": sig_covars,
            "summary_html":           summary.to_html(),
        }
    except Exception as exc:
        print(f"⚠️  Cox PH fitting failed: {exc}")
        return _empty


def run_survival_analysis(
    transactions_df: pd.DataFrame,
    customers_df: pd.DataFrame = None,
    churn_threshold_days: float = 120.0,
) -> dict:
    """
    Full survival analysis pipeline:
      prepare → KM overall → KM by age band (if available) → Cox PH

    Returns {"available": False} if transactions_df is empty.
    """
    if transactions_df is None or transactions_df.empty:
        return {"available": False}

    survival_df = prepare_survival_df(
        transactions_df, customers_df, churn_threshold_days
    )

    km_overall = fit_kaplan_meier(survival_df)

    # Age-banded KM
    km_by_age = None
    if "age" in survival_df.columns:
        survival_df["age_band"] = pd.cut(
            survival_df["age"],
            bins=[0, 25, 35, 45, 100],
            labels=["<25", "25-35", "35-45", "45+"],
        )
        km_by_age = fit_kaplan_meier(survival_df, group_col="age_band")

    # Cox PH — use age if present, otherwise skip
    covariate_cols = []
    if "age" in survival_df.columns:
        covariate_cols.append("age")

    cox = fit_cox_ph(survival_df, covariate_cols)

    n_customers = int(len(survival_df))
    churn_rate  = float(survival_df["event_observed"].mean())

    return {
        "survival_data": survival_df,
        "km_overall":    km_overall,
        "km_by_age":     km_by_age,
        "cox":           cox,
        "n_customers":   n_customers,
        "churn_rate":    churn_rate,
    }


if __name__ == "__main__":
    np.random.seed(42)
    customers = [f"C{i}" for i in range(200)]
    df = pd.DataFrame({
        "customer_id":      np.random.choice(customers, 800),
        "transaction_date": pd.date_range("2020-01-01", periods=800, freq="12h"),
        "price":            np.random.uniform(10, 200, 800),
    })

    result = run_survival_analysis(df, churn_threshold_days=90.0)
    print("Survival analysis available:", result.get("available", True))
    print("Median survival:", result["km_overall"]["median_survival"])
    print("Cox concordance:", result["cox"]["concordance"])
    print("Survival analysis OK")
