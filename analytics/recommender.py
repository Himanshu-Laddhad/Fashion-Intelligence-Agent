"""
Collaborative filtering recommender using cornac MF (ALS substitute).

DEVIATION from CURSOR_TASKS.md:
  The spec imports `implicit.als.AlternatingLeastSquares`.
  `implicit` has no Python 3.13 wheel on Windows; replaced by `cornac.models.MF`.
  The public interface is identical — `_ALSAdapter` wraps cornac MF and exposes
  the same `.recommend(user_idx, user_items_row, N, filter_already_liked_items)` API.
  See AGENT_CONTEXT.md Task 0.1 for full substitution rationale.
"""

import pickle
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

warnings.filterwarnings("ignore")

# ── cornac imports (replaces implicit) ────────────────────────────────────────
from cornac.data import Dataset as CornacDataset
from cornac.models import MF as CornacMF


# ── ALS-compatible adapter ─────────────────────────────────────────────────────

class _ALSAdapter:
    """
    Wraps cornac MF factor matrices to expose an implicit-compatible interface.

    After fitting cornac MF on integer-indexed UIR data, factor matrices are
    stored in our original index space so `u_factors[user_idx]` and
    `i_factors[item_idx]` are directly addressable.
    """

    def __init__(self, u_factors: np.ndarray, i_factors: np.ndarray):
        self._uf = u_factors   # (n_users, k)
        self._if = i_factors   # (n_items, k)

    def recommend(
        self,
        user_idx: int,
        user_items_row,
        N: int = 10,
        filter_already_liked_items: bool = True,
    ) -> tuple:
        """
        Return (item_indices_array, scores_array) for top-N items.

        Compatible with implicit.als.AlternatingLeastSquares.recommend().
        """
        if user_idx >= len(self._uf):
            return np.array([], dtype=int), np.array([])

        scores = self._if @ self._uf[user_idx]   # (n_items,)

        if filter_already_liked_items and hasattr(user_items_row, "indices"):
            scores = scores.copy()
            scores[user_items_row.indices] = -np.inf

        top_n = np.argsort(scores)[::-1][:N]
        return top_n.astype(int), scores[top_n]


# ── public functions ───────────────────────────────────────────────────────────

def build_interaction_matrix(
    transactions_df: pd.DataFrame,
    articles_df: pd.DataFrame = None,
) -> tuple:
    """
    Build a customer × article sparse CSR matrix from transaction data.

    Value = purchase frequency (how many times customer bought article).

    Returns
    -------
    (sparse_matrix, customer_to_idx, article_to_idx, idx_to_article)
    """
    df = transactions_df.copy()
    df["article_id"] = df["article_id"].astype(str)
    df["customer_id"] = df["customer_id"].astype(str)

    customer_ids = sorted(df["customer_id"].unique())
    article_ids  = sorted(df["article_id"].unique())

    customer_to_idx = {c: i for i, c in enumerate(customer_ids)}
    article_to_idx  = {a: i for i, a in enumerate(article_ids)}
    idx_to_article  = {i: a for a, i in article_to_idx.items()}

    counts = (
        df.groupby(["customer_id", "article_id"])
        .size()
        .reset_index(name="count")
    )

    rows = counts["customer_id"].map(customer_to_idx).values
    cols = counts["article_id"].map(article_to_idx).values
    data = counts["count"].values.astype(np.float32)

    matrix = csr_matrix(
        (data, (rows, cols)),
        shape=(len(customer_ids), len(article_ids)),
    )

    return matrix, customer_to_idx, article_to_idx, idx_to_article


def train_als_model(
    interaction_matrix: csr_matrix,
    factors: int = 50,
    iterations: int = 20,
) -> _ALSAdapter:
    """
    Train a Matrix Factorization model on the customer × article matrix.

    Uses cornac MF (ALS substitute). Converts row/col integer indices to
    string IDs for cornac, then re-maps factor matrices back to our index space.

    Returns an _ALSAdapter with an implicit-compatible .recommend() interface.
    """
    cx    = interaction_matrix.tocoo()
    rows  = cx.row.astype(str)
    cols  = cx.col.astype(str)
    data  = cx.data.astype(np.float32)

    uir       = list(zip(rows, cols, data))
    train_set = CornacDataset.from_uir(uir, seed=42)

    model = CornacMF(
        k=factors,
        max_iter=iterations,
        learning_rate=0.01,
        lambda_reg=0.01,
        seed=42,
        verbose=False,
    )
    model.fit(train_set)

    n_users = interaction_matrix.shape[0]
    n_items = interaction_matrix.shape[1]

    u_factors = np.zeros((n_users, factors), dtype=np.float32)
    i_factors = np.zeros((n_items, factors), dtype=np.float32)

    for uid_str, cornac_u in train_set.uid_map.items():
        our_idx = int(uid_str)
        if our_idx < n_users:
            u_factors[our_idx] = model.u_factors[cornac_u]

    for iid_str, cornac_i in train_set.iid_map.items():
        our_idx = int(iid_str)
        if our_idx < n_items:
            i_factors[our_idx] = model.i_factors[cornac_i]

    return _ALSAdapter(u_factors, i_factors)


def recommend_for_customer(
    model: _ALSAdapter,
    customer_id: str,
    customer_to_idx: dict,
    idx_to_article: dict,
    interaction_matrix: csr_matrix,
    n: int = 10,
) -> list:
    """
    Return top-n article_id strings for a single customer.
    Returns [] if customer_id not in the training data.
    """
    user_idx = customer_to_idx.get(str(customer_id))
    if user_idx is None:
        return []

    item_indices, _ = model.recommend(
        user_idx,
        interaction_matrix[user_idx],
        N=n,
        filter_already_liked_items=True,
    )

    return [idx_to_article[int(i)] for i in item_indices if int(i) in idx_to_article]


def recommend_for_segment(
    model: _ALSAdapter,
    segment_customer_ids: list,
    customer_to_idx: dict,
    idx_to_article: dict,
    interaction_matrix: csr_matrix,
    n: int = 10,
) -> list:
    """
    Return top-n article_ids most frequently recommended across a customer segment.

    Samples up to 100 customers from segment_customer_ids for efficiency.
    """
    sample = segment_customer_ids[:100]
    article_counts: Counter = Counter()

    for cid in sample:
        recs = recommend_for_customer(
            model, cid, customer_to_idx, idx_to_article, interaction_matrix, n=n
        )
        article_counts.update(recs)

    return [article for article, _ in article_counts.most_common(n)]


def run_recommender_pipeline(
    transactions_df: pd.DataFrame,
    articles_df: pd.DataFrame = None,
) -> dict:
    """
    Full pipeline: build interaction matrix → train MF model.

    Returns {"available": False} if data is empty or has fewer than 500 rows.
    """
    if transactions_df is None or transactions_df.empty or len(transactions_df) < 500:
        return {"available": False}

    try:
        matrix, customer_to_idx, article_to_idx, idx_to_article = \
            build_interaction_matrix(transactions_df, articles_df)

        model = train_als_model(matrix)

        return {
            "available":          True,
            "model":              model,
            "customer_to_idx":    customer_to_idx,
            "article_to_idx":     article_to_idx,
            "idx_to_article":     idx_to_article,
            "interaction_matrix": matrix,
            "n_customers":        matrix.shape[0],
            "n_articles":         matrix.shape[1],
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    customers = [f"C{i}" for i in range(100)]
    articles  = [f"A{i}" for i in range(50)]
    df = pd.DataFrame({
        "customer_id":      np.random.choice(customers, 600),
        "article_id":       np.random.choice(articles, 600),
        "transaction_date": pd.date_range("2021-01-01", periods=600, freq="12h"),
        "price":            np.random.uniform(10, 100, 600),
    })

    result = run_recommender_pipeline(df)
    print("Recommender available:", result["available"])
    if result["available"]:
        recs = recommend_for_customer(
            result["model"], "C0",
            result["customer_to_idx"], result["idx_to_article"],
            result["interaction_matrix"], n=5,
        )
        print("Recs for C0:", recs)
    print("Recommender OK")
