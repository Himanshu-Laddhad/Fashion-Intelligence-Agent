import math
import pandas as pd
from typing import Optional

WEIGHT_GOOGLE = 0.45
WEIGHT_SOCIAL = 0.25
WEIGHT_RETAIL = 0.30


class TrendVelocityScorer:

    def score_retail_presence(
        self, zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame
    ) -> float:
        """Normalise combined item count to 0-100 (saturates at 20 items)."""
        zara_count   = len(zara_df.dropna(how="all"))   if not zara_df.empty   else 0
        uniqlo_count = len(uniqlo_df.dropna(how="all")) if not uniqlo_df.empty else 0
        total = zara_count + uniqlo_count
        return min(total / 20.0 * 100, 100.0)

    def score_from_google(self, momentum_dict: dict) -> float:
        """Map momentum [-1, 1] → score [0, 100]."""
        momentum = float(momentum_dict.get("momentum", 0.0))
        return (momentum + 1.0) / 2.0 * 100.0

    def score_social(
        self, reddit_post_count: int, avg_upvotes: float = 0.0
    ) -> float:
        """Log-scale post count → 0-100, with optional upvote boost (+10 max)."""
        base = min(
            math.log1p(reddit_post_count) / math.log1p(100) * 100,
            100.0,
        )
        boost = 0.0
        if avg_upvotes > 0:
            boost = min(math.log1p(avg_upvotes) / math.log1p(1000) * 10, 10.0)
        return min(base + boost, 100.0)

    def compute_tvi(
        self,
        google_score: float,
        social_score: float,
        retail_score: float,
    ) -> dict:
        """Weighted TVI with confidence classification."""
        tvi = round(
            WEIGHT_GOOGLE * google_score
            + WEIGHT_SOCIAL * social_score
            + WEIGHT_RETAIL * retail_score,
            2,
        )

        if google_score > 20 and social_score > 20 and retail_score > 20:
            confidence = "high"
        elif tvi > 30:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "tvi":          tvi,
            "google_score": google_score,
            "social_score": social_score,
            "retail_score": retail_score,
            "confidence":   confidence,
        }

    def score_query(
        self,
        query: str,
        zara_df: pd.DataFrame,
        uniqlo_df: pd.DataFrame,
        google_momentum: Optional[dict] = None,
        reddit_count: int = 0,
    ) -> dict:
        """Compute all component scores, then TVI, and return full result dict."""
        if google_momentum is None:
            google_momentum = {"momentum": 0.0}

        google_score = self.score_from_google(google_momentum)
        social_score = self.score_social(reddit_count)
        retail_score = self.score_retail_presence(zara_df, uniqlo_df)

        result = self.compute_tvi(google_score, social_score, retail_score)
        result["query"] = query
        return result


def score_trend(
    query: str,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    google_momentum: Optional[dict] = None,
) -> dict:
    scorer = TrendVelocityScorer()
    return scorer.score_query(query, zara_df, uniqlo_df, google_momentum)


if __name__ == "__main__":
    fake_zara   = pd.DataFrame({"name": ["item"] * 8})
    fake_uniqlo = pd.DataFrame({"name": ["item"] * 6})
    result = score_trend("denim jacket", fake_zara, fake_uniqlo, {"momentum": 0.3})
    print(result)
    assert "tvi" in result
    assert 0 <= result["tvi"] <= 100
    print("TVI scorer OK")
