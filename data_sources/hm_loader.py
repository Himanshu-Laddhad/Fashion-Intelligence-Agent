import pandas as pd
from pathlib import Path
from typing import Optional

_DATA_DIR = Path("data/hm")
_ARTICLES_PATH     = _DATA_DIR / "articles.csv"
_CUSTOMERS_PATH    = _DATA_DIR / "customers.csv"
_TRANSACTIONS_PATH = _DATA_DIR / "transactions_train.csv"

_ARTICLE_COLS = [
    "article_id", "product_type_name", "product_group_name",
    "colour_group_name", "perceived_colour_value_name",
    "perceived_colour_master_name", "section_name",
    "garment_group_name", "detail_desc",
]
_ARTICLE_RENAME = {
    "product_type_name":              "product_type",
    "product_group_name":             "product_group",
    "colour_group_name":              "colour_group",
    "perceived_colour_value_name":    "colour_value",
    "perceived_colour_master_name":   "colour_master",
    "section_name":                   "section",
    "garment_group_name":             "garment_group",
    "detail_desc":                    "description",
}


def check_hm_data_available() -> bool:
    """Return True only when all three H&M CSV files are present."""
    return all(p.exists() for p in (_ARTICLES_PATH, _CUSTOMERS_PATH, _TRANSACTIONS_PATH))


def load_articles(nrows: Optional[int] = None) -> pd.DataFrame:
    """Load H&M articles.csv, keeping and renaming the relevant columns."""
    try:
        df = pd.read_csv(_ARTICLES_PATH, nrows=nrows, dtype={"article_id": str})
        available = [c for c in _ARTICLE_COLS if c in df.columns]
        df = df[available].rename(columns=_ARTICLE_RENAME)
        return df
    except FileNotFoundError:
        print(f"⚠️  articles.csv not found at {_ARTICLES_PATH}")
        return pd.DataFrame()
    except Exception as exc:
        print(f"⚠️  load_articles error: {exc}")
        return pd.DataFrame()


def load_customers(nrows: Optional[int] = None) -> pd.DataFrame:
    """Load H&M customers.csv, keeping only the relevant columns."""
    try:
        df = pd.read_csv(_CUSTOMERS_PATH, nrows=nrows)
        keep = [c for c in ["customer_id", "age", "club_member_status",
                             "fashion_news_frequency"] if c in df.columns]
        return df[keep]
    except FileNotFoundError:
        print(f"⚠️  customers.csv not found at {_CUSTOMERS_PATH}")
        return pd.DataFrame()
    except Exception as exc:
        print(f"⚠️  load_customers error: {exc}")
        return pd.DataFrame()


def load_transactions(nrows: Optional[int] = None) -> pd.DataFrame:
    """Load H&M transactions_train.csv, parsing dates and renaming t_dat."""
    try:
        df = pd.read_csv(
            _TRANSACTIONS_PATH,
            nrows=nrows,
            parse_dates=["t_dat"],
        )
        keep = [c for c in ["t_dat", "customer_id", "article_id", "price",
                             "sales_channel_id"] if c in df.columns]
        df = df[keep].rename(columns={"t_dat": "transaction_date"})
        return df
    except FileNotFoundError:
        print(f"⚠️  transactions_train.csv not found at {_TRANSACTIONS_PATH}")
        return pd.DataFrame()
    except Exception as exc:
        print(f"⚠️  load_transactions error: {exc}")
        return pd.DataFrame()


def load_sample(n_customers: int = 50_000) -> dict:
    """
    Load a random sample of n_customers and their associated data.

    Returns a dict with keys: transactions, articles, customers, n_customers.
    """
    transactions = load_transactions()

    if transactions.empty:
        return {
            "transactions": pd.DataFrame(),
            "articles": pd.DataFrame(),
            "customers": pd.DataFrame(),
            "n_customers": 0,
        }

    all_ids = transactions["customer_id"].unique()
    sample_size = min(n_customers, len(all_ids))
    sampled_ids = pd.Series(all_ids).sample(n=sample_size, random_state=42).values

    txn_sample = transactions[transactions["customer_id"].isin(sampled_ids)].copy()

    articles = load_articles()

    customers = load_customers()
    if not customers.empty and "customer_id" in customers.columns:
        customers = customers[customers["customer_id"].isin(sampled_ids)].copy()

    return {
        "transactions": txn_sample,
        "articles": articles,
        "customers": customers,
        "n_customers": sample_size,
    }


def get_data_summary() -> dict:
    """Return a high-level summary of the H&M dataset availability and size."""
    if not check_hm_data_available():
        return {"available": False}

    transactions = load_transactions()
    customers    = load_customers()
    articles     = load_articles()

    date_range = ["N/A", "N/A"]
    if not transactions.empty and "transaction_date" in transactions.columns:
        date_range = [
            str(transactions["transaction_date"].min().date()),
            str(transactions["transaction_date"].max().date()),
        ]

    return {
        "available":      True,
        "n_customers":    int(customers["customer_id"].nunique()) if not customers.empty else 0,
        "n_articles":     int(len(articles)) if not articles.empty else 0,
        "n_transactions": int(len(transactions)) if not transactions.empty else 0,
        "date_range":     date_range,
    }


if __name__ == "__main__":
    print(get_data_summary())
