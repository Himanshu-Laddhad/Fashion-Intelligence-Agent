import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer = None


def get_model() -> SentenceTransformer:
    """Lazy-load the sentence-transformer model on first use."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(texts: list) -> np.ndarray:
    """
    Encode a list of strings into 384-dim vectors.

    Returns zero matrix for empty input.
    """
    if not texts:
        return np.zeros((len(texts), 384))
    return get_model().encode(texts, show_progress_bar=False)


def embed_fashion_items(
    df: pd.DataFrame,
    text_col: str = "description",
) -> pd.DataFrame:
    """
    Add an `embedding_json` column to df by embedding a combined text field.

    The combined text is: name (if present) + " " + description (or text_col).
    Returns df unchanged if text_col is not in df.columns.
    """
    if text_col not in df.columns:
        return df

    result = df.copy()
    result[text_col] = result[text_col].fillna("")

    if "name" in result.columns:
        combined = (result["name"].fillna("") + " " + result[text_col]).str.strip()
    else:
        combined = result[text_col]

    vectors = embed_text(combined.tolist())
    result["embedding_json"] = [json.dumps(v.tolist()) for v in vectors]
    return result


def find_similar_items(
    query_text: str,
    items_df: pd.DataFrame,
    top_k: int = 5,
) -> pd.DataFrame:
    """
    Return the top_k most similar rows from items_df to query_text.

    Similarity is computed via cosine similarity on embedding_json vectors.
    Returns empty DataFrame if embedding_json column is absent.
    """
    if "embedding_json" not in items_df.columns or items_df.empty:
        return pd.DataFrame()

    query_vec = embed_text([query_text])  # (1, 384)

    item_vecs = np.array([
        json.loads(e) for e in items_df["embedding_json"]
    ])  # (n, 384)

    sims = cosine_similarity(query_vec, item_vecs).flatten()

    result = items_df.copy()
    result["similarity"] = sims
    return (
        result.sort_values("similarity", ascending=False)
        .head(top_k)
        .reset_index(drop=True)
    )


def build_item_similarity_matrix(items_df: pd.DataFrame) -> np.ndarray:
    """
    Compute the full (n_items × n_items) cosine similarity matrix.

    Returns zero matrix if embedding_json is not present.
    """
    if "embedding_json" not in items_df.columns or items_df.empty:
        n = len(items_df)
        return np.zeros((n, n))

    vecs = np.array([json.loads(e) for e in items_df["embedding_json"]])
    return cosine_similarity(vecs)


if __name__ == "__main__":
    df = pd.DataFrame({
        "name": ["denim jacket", "blue jeans", "cotton t-shirt", "silk blouse", "wool coat"],
        "description": [
            "classic blue denim jacket with button closure",
            "slim fit blue denim jeans",
            "soft white cotton t-shirt basic",
            "elegant ivory silk blouse with collar",
            "warm charcoal grey wool winter coat",
        ],
    })

    embedded = embed_fashion_items(df)
    print("Embeddings shape: (5, has embedding_json)")

    similar = find_similar_items("denim casual blue", embedded, top_k=3)
    print("Similar to 'denim casual blue':", similar["name"].tolist())
    print("Embeddings OK")
