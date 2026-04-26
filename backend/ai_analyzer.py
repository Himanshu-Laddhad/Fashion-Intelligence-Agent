"""
AI-Powered Fashion Trend Analysis
Uses whichever LLM is configured in llm_config (Groq).
"""

import asyncio
import json
import re
from typing import Any, Dict, List

from backend.llm_config import LLM_AVAILABLE, MAX_TOKENS, VISION_AVAILABLE, call_llm, call_llm_vision


# ============================================================================
# DASHBOARD COPY
# ============================================================================

async def generate_dashboard_copy(
    filters: Dict[str, str],
    search_phrase: str,
    trend_terms: List[str],
) -> Dict[str, Any]:
    """
    Generate LLM-powered editorial copy for the live trend dashboard.
    Returns: headline, summary, microcopy, normalized_phrase.
    """
    if not LLM_AVAILABLE:
        return fallback_dashboard_copy(filters, search_phrase, trend_terms)

    trend_signals = ", ".join(trend_terms[:5]) if trend_terms else "none"

    messages = [
        {
            "role": "system",
            "content": "You write editorial fashion dashboard copy. Always return valid JSON only.",
        },
        {
            "role": "user",
            "content": f"""You are writing concise editorial copy for a live fashion trend dashboard.

Active filters:
- Class: {filters.get('class') or 'any'}
- Colour: {filters.get('colour') or 'any'}
- Occasion: {filters.get('occasion') or 'any'}
- Material: {filters.get('material') or 'any'}
- Style: {filters.get('style') or 'any'}
- Extra: {filters.get('extra') or 'none'}

Search phrase: {search_phrase}
Live trend signals: {trend_signals}

Return STRICT JSON only with these keys:
{{
  "headline": "short punchy editorial title (max 8 words)",
  "summary": "1-2 sentence plain-English description for the interface",
  "microcopy": "short refreshing status line (max 10 words)",
  "normalized_phrase": "clean searchable phrase for this trend"
}}

Rules:
- headline should be editorial and compelling
- summary should sound like a fashion editor wrote it
- microcopy is a short caption shown below the summary
- normalized_phrase is close to the search phrase but clean
- Return only valid JSON""",
        },
    ]

    loop = asyncio.get_running_loop()
    try:
        response_text = await loop.run_in_executor(None, lambda: call_llm(messages, 400))
        response_text = _strip_markdown_fence(response_text)
        parsed = _extract_json(response_text)
        if all(k in parsed for k in ["headline", "summary", "microcopy", "normalized_phrase"]):
            return parsed
        raise ValueError("Missing required keys in response")
    except (ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"   ⚠️ generate_dashboard_copy error: {exc}")
        return fallback_dashboard_copy(filters, search_phrase, trend_terms)


# ============================================================================
# IMAGE VERIFICATION
# ============================================================================

def _upgrade_pinterest_url(url: str) -> str:
    """Swap Pinterest thumbnail size prefix to 736x for higher resolution."""
    if not isinstance(url, str) or not url or "pinimg.com" not in url:
        return url if isinstance(url, str) else ""
    url = re.sub(r"/\d+x\d*?/", "/736x/", url)
    return url


async def verify_and_caption_images(
    image_urls: List[str],
    search_phrase: str,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """
    Upgrade Pinterest URLs to 736x, then use Groq vision to verify relevance
    and generate a short caption for each image. Falls back to returning all
    images unverified when vision is unavailable.

    Returns up to `limit` relevant images as:
        [{"url": str, "caption": str | None, "verified": bool}]
    """
    upgraded = [_upgrade_pinterest_url(u) for u in image_urls]

    if not VISION_AVAILABLE:
        return [{"url": u, "caption": None, "verified": False} for u in upgraded[:limit]]

    async def _check_one(url: str) -> Dict[str, Any]:
        try:
            import requests as _requests

            resp = _requests.get(
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

            prompt = (
                f'You are a fashion image curator verifying relevance.\n\n'
                f'Search query: "{search_phrase}"\n\n'
                f'Look at this image and respond with STRICT JSON only:\n'
                f'{{"relevant": true or false, "caption": "one descriptive sentence (max 10 words)"}}\n\n'
                f'relevant=true only if the image clearly shows {search_phrase} or very closely related fashion.\n'
                f'relevant=false if the image is blurry, off-topic, or clearly not fashion-related.\n'
                f'Return only valid JSON.'
            )

            loop = asyncio.get_running_loop()
            response_text = await loop.run_in_executor(
                None, lambda: call_llm_vision(prompt, image_bytes, mime)
            )
            parsed = _extract_json(_strip_markdown_fence(response_text))
            return {
                "url": url,
                "caption": str(parsed.get("caption", "")).strip() or None,
                "verified": True,
                "relevant": bool(parsed.get("relevant", True)),
            }
        except Exception as exc:
            print(f"   ⚠️ Image verification failed, skipping ({url[:50]}…): {exc}")
            return {"url": url, "caption": None, "verified": False, "relevant": False}

    results = await asyncio.gather(*[_check_one(u) for u in upgraded])
    relevant = [r for r in results if r.get("relevant", True)]
    return relevant[:limit]


# ============================================================================
# RESPONSE PARSING HELPERS
# ============================================================================

def _strip_markdown_fence(text: str) -> str:
    """Remove ```json ... ``` fences that some models add despite being told not to."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.startswith("```"))
    return text.strip()


def _extract_json(text: str) -> Dict:
    """Extract the first complete JSON object from a string."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")
    return json.loads(text[start:end])


# ============================================================================
# FALLBACK (no LLM)
# ============================================================================

def fallback_dashboard_copy(
    filters: Dict[str, str],
    search_phrase: str,
    trend_terms: List[str],
) -> Dict[str, Any]:
    """Deterministic dashboard copy when the LLM is unavailable."""
    fashion_class = filters.get("class", "fashion item")
    colour = filters.get("colour", "")
    occasion = filters.get("occasion", "")
    material = filters.get("material", "")
    style = filters.get("style", "")
    extra = filters.get("extra", "")

    headline_bits = [bit for bit in [colour, material, fashion_class] if bit]
    headline = " ".join(headline_bits).strip() or "Live Fashion Trends"
    if occasion:
        headline = f"{headline} for {occasion}"

    summary_parts = [f"Live trends for {search_phrase}."]
    if style:
        summary_parts.append(f"The look is leaning {style}.")
    if extra:
        summary_parts.append(f"Extra context: {extra}.")
    if trend_terms:
        summary_parts.append(f"Top signals: {', '.join(trend_terms[:3])}.")

    normalized_phrase = search_phrase
    norm_bits = [bit for bit in [colour, material, fashion_class] if bit]
    if norm_bits:
        normalized_phrase = " ".join(norm_bits).strip()
        if occasion:
            normalized_phrase = f"{normalized_phrase} for {occasion}"
        if style:
            normalized_phrase = f"{normalized_phrase} in a {style} direction"

    return {
        "headline": headline.title(),
        "summary": " ".join(summary_parts),
        "microcopy": f"Refreshing live trends for {headline.lower()}.",
        "normalized_phrase": normalized_phrase,
    }
