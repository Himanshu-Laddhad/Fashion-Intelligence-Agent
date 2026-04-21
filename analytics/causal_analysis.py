import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from scipy.stats import ttest_ind


def create_treatment_flag(
    transactions_df: pd.DataFrame,
    high_tvi_article_ids: list,
) -> pd.DataFrame:
    """
    Flag each customer as treated (1) if they bought at least one trending article.

    Returns DataFrame: customer_id, treated (0/1), n_trending_purchases.
    """
    df = transactions_df.copy()
    df["article_id"] = df["article_id"].astype(str)
    trending_set = set(str(a) for a in high_tvi_article_ids)

    df["is_trending"] = df["article_id"].isin(trending_set).astype(int)

    result = (
        df.groupby("customer_id")
        .agg(n_trending_purchases=("is_trending", "sum"))
        .reset_index()
    )
    result["treated"] = (result["n_trending_purchases"] > 0).astype(int)
    return result


def compute_propensity_scores(
    treatment_df: pd.DataFrame,
    covariate_cols: list,
) -> pd.DataFrame:
    """
    Fit a logistic regression to estimate propensity scores P(treated=1 | covariates).

    Adds propensity_score column to a copy of treatment_df.
    """
    df = treatment_df.copy()

    available = [c for c in covariate_cols if c in df.columns]
    if not available:
        df["propensity_score"] = 0.5
        return df

    X = df[available].fillna(0).values
    y = df["treated"].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(max_iter=1000, random_state=42, C=1.0)
    lr.fit(X_scaled, y)

    df["propensity_score"] = lr.predict_proba(X_scaled)[:, 1]
    return df


def match_samples(
    scored_df: pd.DataFrame,
    caliper: float = 0.05,
) -> pd.DataFrame:
    """
    Greedy 1:1 nearest-neighbour propensity score matching within a caliper.

    Each treated unit is matched to the closest unmatched control unit whose
    propensity score falls within `caliper` distance.

    Returns matched DataFrame with a match_id column added.
    """
    treated  = scored_df[scored_df["treated"] == 1].copy().reset_index(drop=True)
    control  = scored_df[scored_df["treated"] == 0].copy().reset_index(drop=True)

    used_control = set()
    matches = []
    match_id = 0

    # Sort treated by propensity score for slightly better greedy coverage
    treated = treated.sort_values("propensity_score").reset_index(drop=True)
    control_scores = control["propensity_score"].values

    for _, t_row in treated.iterrows():
        t_score = t_row["propensity_score"]
        distances = np.abs(control_scores - t_score)

        # Find closest unused control within caliper
        sorted_idx = np.argsort(distances)
        matched = False
        for c_idx in sorted_idx:
            if c_idx in used_control:
                continue
            if distances[c_idx] <= caliper:
                used_control.add(c_idx)
                t_copy = t_row.to_dict()
                c_copy = control.iloc[c_idx].to_dict()
                t_copy["match_id"] = match_id
                c_copy["match_id"] = match_id
                matches.append(t_copy)
                matches.append(c_copy)
                match_id += 1
                matched = True
                break
        # Unmatched treated units are silently dropped (standard PSM behaviour)

    if not matches:
        return pd.DataFrame(columns=list(scored_df.columns) + ["match_id"])

    return pd.DataFrame(matches).reset_index(drop=True)


def compute_ate(
    matched_df: pd.DataFrame,
    outcome_col: str,
) -> dict:
    """
    Compute Average Treatment Effect (ATE) on matched pairs via t-test.

    Returns ATE, test statistics, and group means.
    """
    treated_vals = matched_df.loc[matched_df["treated"] == 1, outcome_col].dropna()
    control_vals = matched_df.loc[matched_df["treated"] == 0, outcome_col].dropna()

    if len(treated_vals) == 0 or len(control_vals) == 0:
        return {
            "ate": 0.0, "t_stat": 0.0, "p_value": 1.0,
            "significant": False,
            "n_treated": 0, "n_control": 0,
            "treated_mean": 0.0, "control_mean": 0.0,
        }

    t_stat, p_value = ttest_ind(treated_vals, control_vals)
    treated_mean = float(treated_vals.mean())
    control_mean = float(control_vals.mean())

    return {
        "ate":           float(treated_mean - control_mean),
        "t_stat":        float(t_stat),
        "p_value":       float(p_value),
        "significant":   bool(p_value < 0.05),
        "n_treated":     int(len(treated_vals)),
        "n_control":     int(len(control_vals)),
        "treated_mean":  treated_mean,
        "control_mean":  control_mean,
    }


def run_causal_analysis(
    transactions_df: pd.DataFrame,
    churn_df: pd.DataFrame,
    high_tvi_article_ids: list,
    covariate_cols: list = None,
) -> dict:
    """
    Full PSM pipeline to test whether trending-item buyers churn less.

    Outcome: churned (binary 0/1 from churn_df).
    Covariates default to per-customer frequency and monetary aggregates.

    Returns {"available": False} when inputs are insufficient.
    """
    if (
        transactions_df is None or transactions_df.empty
        or churn_df is None or churn_df.empty
        or not high_tvi_article_ids
    ):
        return {"available": False}

    # ── transaction-level covariates ─────────────────────────────────────────
    txn_agg = (
        transactions_df.groupby("customer_id")
        .agg(frequency=("customer_id", "count"),
             monetary=("price", "sum"))
        .reset_index()
    )

    treatment = create_treatment_flag(transactions_df, high_tvi_article_ids)
    treatment = treatment.merge(txn_agg, on="customer_id", how="left")

    # Merge churn outcome
    churn_slim = churn_df[["customer_id", "churned"]].copy()
    churn_slim["churned"] = churn_slim["churned"].astype(int)
    merged = treatment.merge(churn_slim, on="customer_id", how="inner")

    if merged.empty:
        return {"available": False}

    if covariate_cols is None:
        covariate_cols = ["frequency", "monetary"]

    # ── PSM pipeline ─────────────────────────────────────────────────────────
    scored  = compute_propensity_scores(merged, covariate_cols)
    matched = match_samples(scored)

    if matched.empty:
        return {
            "available": False,
            "reason": "No matches found within caliper — try increasing caliper",
        }

    ate_result = compute_ate(matched, outcome_col="churned")

    # ── interpretation string ─────────────────────────────────────────────────
    n_treated = ate_result["n_treated"]
    n_control = ate_result["n_control"]
    ate       = ate_result["ate"]
    pval      = ate_result["p_value"]

    if ate_result["significant"]:
        direction = "lower" if ate < 0 else "higher"
        pct       = abs(ate_result["treated_mean"] - ate_result["control_mean"]) * 100
        interpretation = (
            f"Trending-item buyers have {pct:.1f}% {direction} churn rate "
            f"(p={pval:.3f}, n={n_treated} treated / {n_control} control)"
        )
    else:
        interpretation = (
            f"No significant difference in churn between trending buyers and controls "
            f"(ATE={ate:.3f}, p={pval:.3f})"
        )

    return {
        "available":     True,
        "ate_result":    ate_result,
        "matched_df":    matched,
        "n_treated":     n_treated,
        "n_control":     n_control,
        "interpretation": interpretation,
    }


if __name__ == "__main__":
    print("Causal analysis module loaded OK")
    print("Run with H&M data for full PSM analysis")
