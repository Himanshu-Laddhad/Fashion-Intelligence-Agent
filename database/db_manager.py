import duckdb
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone


class DatabaseManager:
    def __init__(self, db_path: str = "outputs/fashion_intelligence.duckdb"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)
        schema_sql = (Path(__file__).parent / "schema.sql").read_text()
        self.conn.execute(schema_sql)

    # ── context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── writes ───────────────────────────────────────────────────────────────

    def save_trend_snapshot(self, query: str, source: str, df: pd.DataFrame) -> int:
        raw = df.to_json(orient="records")
        self.conn.execute(
            """
            INSERT INTO trend_snapshots (query, source, timestamp, item_count, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [query, source, datetime.now(timezone.utc), len(df), raw],
        )
        row_id = self.conn.execute(
            "SELECT MAX(id) FROM trend_snapshots WHERE query=? AND source=?",
            [query, source],
        ).fetchone()[0]
        return row_id

    def save_trend_score(
        self,
        query: str,
        tvi_score: float,
        component_scores: dict,
        confidence: str,
    ) -> int:
        self.conn.execute(
            """
            INSERT INTO trend_scores
                (query, scored_at, tvi_score, google_trend_score,
                 social_score, retail_score, confidence, forecast_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                query,
                datetime.now(timezone.utc),
                tvi_score,
                component_scores.get("google"),
                component_scores.get("social"),
                component_scores.get("retail"),
                confidence,
                None,
            ],
        )
        row_id = self.conn.execute(
            "SELECT MAX(id) FROM trend_scores WHERE query=?", [query]
        ).fetchone()[0]
        return row_id

    def save_google_trends(
        self, query: str, interest_df: pd.DataFrame, related: dict
    ) -> int:
        interest_json = interest_df.to_json(orient="records")
        related_json = json.dumps(related)
        self.conn.execute(
            """
            INSERT INTO google_trends_raw (query, fetched_at, interest_over_time, related_queries)
            VALUES (?, ?, ?, ?)
            """,
            [query, datetime.now(timezone.utc), interest_json, related_json],
        )
        row_id = self.conn.execute(
            "SELECT MAX(id) FROM google_trends_raw WHERE query=?", [query]
        ).fetchone()[0]
        return row_id

    def save_fashion_items(self, query: str, source: str, df: pd.DataFrame) -> int:
        columns = ["source", "query", "scraped_at", "name", "color",
                   "material", "price", "image_url", "description", "embedding"]
        now = datetime.now(timezone.utc)
        rows = []
        for _, row in df.iterrows():
            rows.append([
                source,
                query,
                now,
                row.get("name") if "name" in df.columns else None,
                row.get("color") if "color" in df.columns else None,
                row.get("material") if "material" in df.columns else None,
                row.get("price") if "price" in df.columns else None,
                row.get("image_url") if "image_url" in df.columns else None,
                row.get("description") if "description" in df.columns else None,
                row.get("embedding") if "embedding" in df.columns else None,
            ])
        self.conn.executemany(
            """
            INSERT INTO fashion_items
                (source, query, scraped_at, name, color, material,
                 price, image_url, description, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    # ── reads ────────────────────────────────────────────────────────────────

    def get_trend_history(self, query: str, days: int = 90) -> pd.DataFrame:
        result = self.conn.execute(
            """
            SELECT * FROM trend_scores
            WHERE query = ?
              AND scored_at >= NOW() - INTERVAL (?) DAY
            ORDER BY scored_at
            """,
            [query, days],
        ).fetchdf()
        return result

    def get_fashion_items(self, query: str, source: str = None) -> pd.DataFrame:
        if source is not None:
            result = self.conn.execute(
                "SELECT * FROM fashion_items WHERE query=? AND source=? ORDER BY scraped_at",
                [query, source],
            ).fetchdf()
        else:
            result = self.conn.execute(
                "SELECT * FROM fashion_items WHERE query=? ORDER BY scraped_at",
                [query],
            ).fetchdf()
        return result

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    with DatabaseManager() as db:
        print("DB initialized OK")
