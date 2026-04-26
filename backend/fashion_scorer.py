"""Fashion image scoring and ranking.

This module computes a Trend Match Fashion Score for images by combining:
- LLM vision scoring (trend/style/quality + matched terms)
- Rule-based trend and freshness signals from Google Trends terms
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import requests

from backend.llm_config import VISION_AVAILABLE, call_llm_vision


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty response")

    # Try direct JSON parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object in text.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")

    return json.loads(text[start : end + 1])


def _normalize_term_scores(trend_term_scores: Dict[str, float]) -> Dict[str, float]:
    if not trend_term_scores:
        return {}

    values = [float(v) for v in trend_term_scores.values()]
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1.0)

    return {k.lower(): ((float(v) - min_v) / span) * 100.0 for k, v in trend_term_scores.items()}


def _rule_trend_match_score(text: str, trend_terms: List[str], norm_scores: Dict[str, float]) -> float:
    blob = (text or "").lower()
    if not blob or not trend_terms:
        return 45.0

    matched_scores: List[float] = []
    for term in trend_terms:
        t = (term or "").strip().lower()
        if not t:
            continue
        if t in blob:
            matched_scores.append(norm_scores.get(t, 60.0))

    if not matched_scores:
        return 42.0

    return _clamp(sum(matched_scores) / len(matched_scores))


def _freshness_score(matched_terms: List[str], norm_scores: Dict[str, float]) -> float:
    if not matched_terms:
        return 45.0

    vals: List[float] = []
    for term in matched_terms:
        t = (term or "").strip().lower()
        if not t:
            continue
        vals.append(norm_scores.get(t, 55.0))

    if not vals:
        return 45.0

    return _clamp(sum(vals) / len(vals))


def _build_prompt(search_phrase: str, trend_terms: List[str], trend_term_scores: Dict[str, float]) -> str:
    ranked_terms = ", ".join([f"{k} ({int(v)})" for k, v in list(trend_term_scores.items())[:10]])
    terms_text = ", ".join(trend_terms[:10]) if trend_terms else "none"

    return (
        "You are a fashion trend evaluator. "
        "Assess how well this image matches current fashion trends.\n\n"
        f"Search phrase: {search_phrase}\n"
        f"Current trend terms: {terms_text}\n"
        f"Trend term strengths: {ranked_terms or 'none'}\n\n"
        "Return STRICT JSON only with this schema:\n"
        "{\n"
        '  "relevant": true,\n'
        '  "trend_match": 0-100,\n'
        '  "style_match": 0-100,\n'
        '  "quality": 0-100,\n'
        '  "matched_terms": ["term1", "term2"],\n'
        '  "reason": "max 15 words"\n'
        "}\n\n"
        "Scoring guidance:\n"
        "- trend_match: alignment with current trend terms and search phrase\n"
        "- style_match: aesthetic/style compatibility with trend direction\n"
        "- quality: clarity, framing, visual usability\n"
        "Return valid JSON only."
    )


async def _score_one_image(
    image: Dict[str, Any],
    search_phrase: str,
    trend_terms: List[str],
    norm_scores: Dict[str, float],
    trend_term_scores: Dict[str, float],
) -> Dict[str, Any]:
    url = image.get("url")
    caption = image.get("caption") or ""
    description = image.get("description") or ""
    text_blob = f"{caption} {description}".strip()

    rule_trend = _rule_trend_match_score(text_blob, trend_terms, norm_scores)

    llm_trend = None
    style_match = 60.0
    quality = 60.0
    matched_terms: List[str] = []
    reason = "Rule-based scoring fallback"

    if VISION_AVAILABLE and isinstance(url, str) and url:
        try:
            resp = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.pinterest.com/",
                },
                timeout=8,
            )
            resp.raise_for_status()
            image_bytes = resp.content
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip() or "image/jpeg"

            prompt = _build_prompt(search_phrase, trend_terms, trend_term_scores)
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, lambda: call_llm_vision(prompt, image_bytes, mime, 220))
            parsed = _extract_json(raw)

            llm_trend = _clamp(parsed.get("trend_match", rule_trend))
            style_match = _clamp(parsed.get("style_match", 60.0))
            quality = _clamp(parsed.get("quality", 60.0))
            mt = parsed.get("matched_terms", [])
            if isinstance(mt, list):
                matched_terms = [str(x).strip() for x in mt if str(x).strip()]
            reason = str(parsed.get("reason", reason)).strip()[:120] or reason

            # If model says irrelevant, penalize heavily but keep image in ranked list.
            if parsed.get("relevant") is False:
                quality = min(quality, 35.0)
                style_match = min(style_match, 35.0)
        except Exception:
            pass

    freshness = _freshness_score(matched_terms, norm_scores)

    combined_trend = rule_trend if llm_trend is None else (0.6 * llm_trend + 0.4 * rule_trend)

    fashion_score = _clamp(
        0.45 * combined_trend
        + 0.25 * style_match
        + 0.20 * freshness
        + 0.10 * quality
    )

    return {
        **image,
        "fashion_score": round(fashion_score, 1),
        "trend_match": round(combined_trend, 1),
        "style_match": round(style_match, 1),
        "freshness": round(freshness, 1),
        "quality": round(quality, 1),
        "score_reason": reason,
    }


async def score_and_rank_images(
    images: List[Dict[str, Any]],
    search_phrase: str,
    trend_terms: Optional[List[str]] = None,
    trend_term_scores: Optional[Dict[str, float]] = None,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """Score images with a hybrid fashion score and return the top ranked images."""
    if not images:
        return []

    trend_terms = [t for t in (trend_terms or []) if isinstance(t, str) and t.strip()]
    trend_term_scores = trend_term_scores or {}
    norm_scores = _normalize_term_scores(trend_term_scores)

    scored = await asyncio.gather(
        *[
            _score_one_image(img, search_phrase, trend_terms, norm_scores, trend_term_scores)
            for img in images
            if img.get("url")
        ]
    )

    ranked = sorted(scored, key=lambda x: x.get("fashion_score", 0.0), reverse=True)
    if top_k and top_k > 0:
        return ranked[:top_k]
    return ranked
