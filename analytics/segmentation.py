import json
import warnings
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

_RFM_FEATURES = ["recency", "frequency", "monetary"]


def find_optimal_k(
    rfm_df: pd.DataFrame, k_range: range = range(2, 9)
) -> dict:
    """
    Evaluate K-Means for each k in k_range and return the k with the best
    silhouette score along with per-k diagnostics.
    """
    X = rfm_df[_RFM_FEATURES].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    inertias          = []
    silhouette_scores = []

    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(float(km.inertia_))
        silhouette_scores.append(float(silhouette_score(X_scaled, labels)))

    best_idx  = int(np.argmax(silhouette_scores))
    optimal_k = list(k_range)[best_idx]

    return {
        "optimal_k":         optimal_k,
        "inertias":          inertias,
        "silhouette_scores": silhouette_scores,
        "k_range":           list(k_range),
    }


def fit_kmeans_pipeline(
    rfm_df: pd.DataFrame, n_clusters: int = None
) -> tuple:
    """
    Build and fit a StandardScaler → KMeans pipeline on RFM features.

    Returns
    -------
    (fitted_pipeline, cluster_labels_array, k_info_dict)
    """
    if n_clusters is None:
        k_info     = find_optimal_k(rfm_df)
        n_clusters = k_info["optimal_k"]
    else:
        k_info = {"optimal_k": n_clusters}

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("kmeans", KMeans(n_clusters=n_clusters, random_state=42, n_init=10)),
    ])

    X      = rfm_df[_RFM_FEATURES].values
    labels = pipe.fit_predict(X)

    return pipe, labels, k_info


def profile_clusters(
    rfm_df: pd.DataFrame, cluster_labels: np.ndarray
) -> pd.DataFrame:
    """
    Compute mean RFM values and cluster size per cluster.

    Returns a profile DataFrame indexed by cluster_id.
    """
    df = rfm_df.copy()
    df["cluster_id"] = cluster_labels

    agg_cols = [c for c in ["recency", "frequency", "monetary", "rfm_score"] if c in df.columns]

    profile = (
        df.groupby("cluster_id")[agg_cols]
        .mean()
        .round(2)
        .reset_index()
    )
    sizes = df.groupby("cluster_id").size().reset_index(name="cluster_size")
    profile = profile.merge(sizes, on="cluster_id")
    return profile


def assign_cluster_names(profile_df: pd.DataFrame) -> dict:
    """
    Heuristically assign a business label to each cluster based on
    the relative ranking of recency, frequency, and monetary means.

    Lower recency (more recent) is better.
    Higher frequency and monetary are better.
    """
    df = profile_df.copy()
    n  = len(df)

    # Rank each metric relative to other clusters (1 = best for that metric)
    df["r_rank"] = df["recency"].rank(ascending=True)    # low recency → rank 1 (best)
    df["f_rank"] = df["frequency"].rank(ascending=False) # high freq   → rank 1 (best)
    df["m_rank"] = df["monetary"].rank(ascending=False)  # high $      → rank 1 (best)

    names = {}
    for _, row in df.iterrows():
        cid   = int(row["cluster_id"])
        r, f, m = row["r_rank"], row["f_rank"], row["m_rank"]
        mid   = (n + 1) / 2  # midpoint rank

        if r == 1 and f == 1 and m == 1:
            label = "VIP / Champions"
        elif r == n:          # highest recency days → least recent
            label = "Recently Lost"
        elif f == n and m == n:
            label = "Dormant"
        elif abs(r - mid) <= 1 and abs(f - mid) <= 1:
            label = "Core Customers"
        else:
            label = f"Segment {cid}"

        names[cid] = label

    return names


def run_segmentation(rfm_df: pd.DataFrame) -> dict:
    """
    Full segmentation pipeline: optimal-K search → KMeans fit →
    cluster profiling → name assignment.

    Returns a safe empty result dict if rfm_df is empty or too small.
    """
    _empty = {
        "rfm_with_clusters": pd.DataFrame(),
        "cluster_profiles":  pd.DataFrame(),
        "cluster_names":     {},
        "k_info":            {},
        "n_clusters":        0,
    }

    if rfm_df is None or rfm_df.empty or len(rfm_df) < 10:
        return _empty

    try:
        pipe, labels, k_info = fit_kmeans_pipeline(rfm_df)
        profiles             = profile_clusters(rfm_df, labels)
        names                = assign_cluster_names(profiles)

        rfm_with_clusters             = rfm_df.copy()
        rfm_with_clusters["cluster_id"]   = labels
        rfm_with_clusters["cluster_name"] = [names.get(int(l), f"Segment {l}") for l in labels]

        return {
            "rfm_with_clusters": rfm_with_clusters,
            "cluster_profiles":  profiles,
            "cluster_names":     names,
            "k_info":            k_info,
            "n_clusters":        int(k_info["optimal_k"]),
        }
    except Exception as exc:
        print(f"⚠️  Segmentation failed: {exc}")
        return _empty


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from rfm import build_rfm_pipeline

    np.random.seed(42)
    customers = [f"C{i}" for i in range(500)]
    df = pd.DataFrame({
        "customer_id":      np.random.choice(customers, 2000),
        "transaction_date": pd.date_range("2021-01-01", periods=2000, freq="4h"),
        "price":            np.random.uniform(5, 300, 2000),
    })

    rfm    = build_rfm_pipeline(df)
    result = run_segmentation(rfm)
    print("Optimal K:", result["n_clusters"])
    print("Cluster profiles:\n", result["cluster_profiles"])
    print("Segmentation OK")
