"""SQLite cache for trend data and Pinterest images.

Entries are wiped and rewritten on each manual refresh.
"""

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

DB_PATH = Path("outputs/trend_cache.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS trend_data (
            query       TEXT NOT NULL,
            timeframe   TEXT NOT NULL,
            ts_json     TEXT,
            region_json TEXT,
            terms_json  TEXT,
            PRIMARY KEY (query, timeframe)
        );
        CREATE TABLE IF NOT EXISTS pinterest_images (
            url         TEXT PRIMARY KEY,
            search_term TEXT,
            description TEXT,
            caption     TEXT,
            verified    INTEGER DEFAULT 0
        );
    """)
    return con


def clear() -> None:
    with _connect() as con:
        con.execute("DELETE FROM trend_data")
        con.execute("DELETE FROM pinterest_images")


# ── Trend data ────────────────────────────────────────────────────────────────

def has_trend(query: str, timeframe: str) -> bool:
    with _connect() as con:
        return con.execute(
            "SELECT 1 FROM trend_data WHERE query=? AND timeframe=?",
            (query, timeframe),
        ).fetchone() is not None


def save_trend(
    query: str,
    timeframe: str,
    ts_df: pd.DataFrame,
    region_df: pd.DataFrame,
    terms_df: pd.DataFrame,
) -> None:
    def _ser(df: pd.DataFrame) -> Optional[str]:
        if df is None or df.empty:
            return None
        return df.reset_index().to_json(orient="records", date_format="iso")

    with _connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO trend_data VALUES (?,?,?,?,?)",
            (query, timeframe, _ser(ts_df), _ser(region_df), _ser(terms_df)),
        )


def load_trend(
    query: str, timeframe: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with _connect() as con:
        row = con.execute(
            "SELECT ts_json, region_json, terms_json FROM trend_data WHERE query=? AND timeframe=?",
            (query, timeframe),
        ).fetchone()

    if not row:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def _deser(s: str | None) -> pd.DataFrame:
        return pd.read_json(s, orient="records") if s else pd.DataFrame()

    def _deser_ts(s: str | None) -> pd.DataFrame:
        if not s:
            return pd.DataFrame()
        df = pd.read_json(s, orient="records")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        return df

    return _deser_ts(row[0]), _deser(row[1]), _deser(row[2])


# ── Pinterest images ──────────────────────────────────────────────────────────

def has_images(search_term: str) -> bool:
    with _connect() as con:
        return con.execute(
            "SELECT 1 FROM pinterest_images WHERE search_term=? LIMIT 1",
            (search_term,),
        ).fetchone() is not None


def save_images(search_term: str, images: list[dict]) -> None:
    with _connect() as con:
        con.executemany(
            "INSERT OR IGNORE INTO pinterest_images (url, search_term, description, caption, verified) VALUES (?,?,?,?,?)",
            [
                (
                    img.get("url"),
                    search_term,
                    img.get("description"),
                    img.get("caption"),
                    int(img.get("verified", False)),
                )
                for img in images
                if img.get("url")
            ],
        )


def load_images(search_term: str) -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT url, description, caption, verified FROM pinterest_images WHERE search_term=?",
            (search_term,),
        ).fetchall()
    return [
        {"url": r[0], "description": r[1], "caption": r[2], "verified": bool(r[3])}
        for r in rows
    ]
