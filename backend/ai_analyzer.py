"""
AI-Powered Fashion Trend Analysis
Provider-agnostic: uses whichever LLM is configured in llm_config (Gemini or Groq).
"""

import asyncio
import json
from typing import Any, Dict, List

import pandas as pd

import re

from backend.llm_config import LLM_AVAILABLE, MAX_TOKENS, VISION_AVAILABLE, call_llm, call_llm_vision


# ============================================================================
# PUBLIC ASYNC ANALYSIS FUNCTIONS
# ============================================================================

async def analyze_fashion_data_ai_driven(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    AI-powered trend analysis with color and material detection.
    Colors and materials extracted from actual scraped data, then enriched by the LLM.
    """
    print("   🤖 Running AI trend analysis...")

    data_summary = prepare_comprehensive_data_summary(
        query, pinterest_df, zara_df, uniqlo_df, vogue_df
    )

    if LLM_AVAILABLE:
        try:
            analysis = await _analyze_with_llm(query, data_summary)
            print("   ✓ AI analysis complete (detected actual market data)")
            return analysis
        except Exception as e:
            print(f"   ⚠️ LLM error during analysis: {e}")
            print("   Falling back to data-driven analysis...")

    return fallback_analysis_data_driven(query, pinterest_df, zara_df, uniqlo_df, vogue_df)


async def customize_for_brands_ai_driven(
    query: str,
    trend_analysis: Dict,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    AI-powered brand customization using detected market data.
    Colors and materials come from the LLM analysis, not hardcoded values.
    """
    print("   🤖 Generating AI-driven brand customizations...")

    zara_products = extract_product_data(zara_df, limit=3)
    uniqlo_products = extract_product_data(uniqlo_df, limit=3)

    if LLM_AVAILABLE:
        try:
            brands = await _customize_with_llm(
                query, trend_analysis, zara_products, uniqlo_products
            )
            print("   ✓ Brand customization complete")
            return brands
        except Exception as e:
            print(f"   ⚠️ LLM error during brand customization: {e}")
            print("   Falling back to data-driven customization...")

    return fallback_brand_customization_ai_driven(
        query, trend_analysis, zara_products, uniqlo_products
    )


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
    Upgrade Pinterest URLs to 736x, then use Groq's Llama 4 Scout vision model to verify relevance
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
        except (_requests.Timeout, _requests.ConnectionError) as exc:
            print(f"   ⚠️ Image download timeout/connection error ({url[:50]}…): {exc}")
            return {"url": url, "caption": None, "verified": False, "relevant": True}
        except Exception as exc:
            print(f"   ⚠️ Image verification skipped ({url[:50]}…): {exc}")
            return {"url": url, "caption": None, "verified": False, "relevant": True}

    results = await asyncio.gather(*[_check_one(u) for u in upgraded])
    relevant = [r for r in results if r.get("relevant", True)]
    return relevant[:limit]


# ============================================================================
# INTERNAL LLM HELPERS
# ============================================================================

async def _analyze_with_llm(query: str, data_summary: Dict) -> Dict[str, Any]:
    """Call the LLM to analyze fashion trends from scraped market data."""

    prompt = f"""You are an expert AI fashion trend analyst with deep market intelligence.

MARKET DATA FROM REAL SOURCES:
Query: "{query}"

DATA COLLECTED:
- Pinterest Images: {data_summary['image_count']} visual references
- Zara Products: {data_summary['zara_count']} items analyzed
- Uniqlo Products: {data_summary['uniqlo_count']} items analyzed
- Vogue Articles: {data_summary['vogue_count']} editorial pieces

ACTUAL DETECTED DATA FROM MARKET:
Colors found: {data_summary['detected_colors']}
Materials found: {data_summary['detected_materials']}
Product names: {data_summary['product_names']}
Editorial focus: {data_summary['editorial_themes']}

YOUR TASK:
Analyze this REAL market data and provide intelligent trend insights for "{query}".

INSTRUCTIONS:
1. Identify ACTUAL trends from the real scraped data above
2. Validate colors and materials from the market detection
3. Suggest additional complementary colors/materials based on fashion science
4. Identify aesthetic vibes from product positioning and editorial coverage
5. Be data-driven - only suggest trends that align with actual findings

Return STRICT JSON format (no markdown):
{{
  "key_trends": ["trend1", "trend2", "trend3", "trend4", "trend5"],
  "dominant_palette": ["color1", "color2", "color3", "color4", "color5", "color6"],
  "materials": ["material1", "material2", "material3", "material4", "material5"],
  "aesthetic_vibes": ["vibe1", "vibe2", "vibe3", "vibe4"],
  "market_confidence": "high/medium/low",
  "analysis_note": "Brief insight on trend strength"
}}

RULES:
- Colors MUST include detected market colors
- Materials MUST include detected market materials
- Add complementary items based on fashion theory
- Return ONLY JSON"""

    messages = [
        {
            "role": "system",
            "content": "You are a fashion trend analyst with access to real market data. Analyze trends scientifically based on actual data. Always respond with valid JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    loop = asyncio.get_running_loop()
    response_text = await loop.run_in_executor(None, lambda: call_llm(messages, MAX_TOKENS))

    response_text = _strip_markdown_fence(response_text)
    analysis = _extract_json(response_text)
    analysis["query"] = query

    required_keys = ["key_trends", "dominant_palette", "materials", "aesthetic_vibes"]
    if not all(k in analysis for k in required_keys):
        print(f"   ⚠️ LLM analysis missing keys: {[k for k in required_keys if k not in analysis]}")
        # Provide sensible defaults
        return {
            "key_trends": [query],
            "dominant_palette": ["neutral", "black", "white"],
            "materials": ["cotton", "denim", "wool"],
            "aesthetic_vibes": ["contemporary"],
            "market_confidence": "low",
            "analysis_note": "LLM response incomplete; using defaults",
            "query": query,
        }

    return analysis


async def _customize_with_llm(
    query: str,
    trend_analysis: Dict,
    zara_products: List[Dict],
    uniqlo_products: List[Dict],
) -> Dict[str, Any]:
    """Call the LLM to create brand-specific strategies from detected market trends."""

    detected_colors = ", ".join(trend_analysis.get("dominant_palette", [])[:6])
    detected_materials = ", ".join(trend_analysis.get("materials", [])[:6])

    prompt = f"""You are a luxury brand strategy consultant analyzing "{query}" market data.

MARKET INTELLIGENCE:
- Query: "{query}"
- Detected Colors: {detected_colors}
- Detected Materials: {detected_materials}
- Aesthetic Vibes: {', '.join(trend_analysis.get('aesthetic_vibes', [])[:4])}
- Key Trends: {', '.join(trend_analysis.get('key_trends', [])[:5])}

BRAND PROFILES TO CUSTOMIZE FOR:
1. OLD NAVY - Mass market (18-35), value-conscious, family-focused
2. BANANA REPUBLIC - Premium (30-50), professional, luxury-minded
3. GAP - Mainstream (25-45), classic American, timeless

YOUR TASK:
Create UNIQUE brand interpretations of "{query}" that:
1. Respect detected market colors and materials
2. Adapt them for each brand's positioning
3. Create distinct color palettes per brand
4. Suggest premium vs accessible materials
5. Align with brand DNA while following market trends

CRITICAL: Do NOT use hardcoded values. DERIVE everything from the market data above.

Return STRICT JSON:
{{
  "old_navy": {{
    "summary": "2-3 sentence interpretation for value brand, family appeal",
    "colors": ["color1", "color2", "color3", "color4", "color5"],
    "materials": ["budget_material1", "material2", "material3", "material4"],
    "vibes": ["vibe1", "vibe2", "vibe3", "vibe4"],
    "target": "Value-conscious families and young adults 18-35",
    "price_positioning": "Accessible entry-level pricing"
  }},
  "banana_republic": {{
    "summary": "2-3 sentence interpretation for premium brand, professional",
    "colors": ["luxury_color1", "color2", "color3", "color4", "color5"],
    "materials": ["premium_material1", "luxury_material2", "high_end_material3", "material4"],
    "vibes": ["vibe1", "vibe2", "vibe3", "vibe4"],
    "target": "Professional urban adults 30-50 with high disposable income",
    "price_positioning": "Premium positioning with luxury materials"
  }},
  "gap": {{
    "summary": "2-3 sentence interpretation for mainstream brand, American classic",
    "colors": ["classic_color1", "color2", "color3", "color4", "color5"],
    "materials": ["quality_material1", "material2", "material3", "material4"],
    "vibes": ["vibe1", "vibe2", "vibe3", "vibe4"],
    "target": "Modern mainstream consumers 25-45",
    "price_positioning": "Mid-range quality and value"
  }}
}}

RULES:
- Colors must be variations of detected colors
- Materials must be adapted from detected materials
- No hardcoded responses - everything AI-derived
- Return ONLY JSON"""

    messages = [
        {
            "role": "system",
            "content": "You are a brand strategy consultant. Create AI-derived strategies based on market data. Always respond with valid JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    loop = asyncio.get_running_loop()
    response_text = await loop.run_in_executor(None, lambda: call_llm(messages, MAX_TOKENS * 2))

    response_text = _strip_markdown_fence(response_text)
    brands = _extract_json(response_text)

    required_brands = ["old_navy", "banana_republic", "gap"]
    if not all(brand in brands for brand in required_brands):
        raise ValueError("Missing required brand keys in LLM response")

    brands["old_navy"]["products"] = zara_products[:2]
    brands["banana_republic"]["products"] = zara_products[:3]
    brands["gap"]["products"] = uniqlo_products[:3]

    return brands


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
# DATA PREPARATION
# ============================================================================

def prepare_comprehensive_data_summary(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Extract colors, materials, and themes from scraped data for LLM context."""

    colors: List[str] = []
    materials: List[str] = []
    product_names: List[str] = []
    editorial_themes: List[str] = []

    for df in [zara_df, uniqlo_df]:
        if not df.empty and "color" in df.columns:
            colors.extend(df["color"].dropna().tolist())

    for df in [zara_df, uniqlo_df]:
        if not df.empty and "material" in df.columns:
            materials.extend(df["material"].dropna().tolist())

    for df in [zara_df, uniqlo_df]:
        if not df.empty and "name" in df.columns:
            product_names.extend(df["name"].dropna().tolist())

    if not vogue_df.empty:
        if "title" in vogue_df.columns:
            editorial_themes.extend(vogue_df["title"].dropna().tolist())
        if "text" in vogue_df.columns:
            editorial_themes.extend(vogue_df["text"].dropna().tolist()[:3])

    colors = list({str(c).lower().strip() for c in colors if pd.notna(c) and str(c).strip()})[:15]
    materials = list({str(m).lower().strip() for m in materials if pd.notna(m) and str(m).strip()})[:15]
    product_names = [str(n) for n in product_names if pd.notna(n)][:10]

    return {
        "image_count": len(pinterest_df),
        "zara_count": len(zara_df),
        "uniqlo_count": len(uniqlo_df),
        "vogue_count": len(vogue_df),
        "detected_colors": ", ".join(colors) if colors else "multiple colors",
        "detected_materials": ", ".join(materials) if materials else "various materials",
        "product_names": ", ".join(product_names) if product_names else query,
        "editorial_themes": ", ".join([str(t)[:100] for t in editorial_themes[:3]]) if editorial_themes else "fashion trends",
    }


def extract_product_data(df: pd.DataFrame, limit: int = 3) -> List[Dict]:
    """Extract product data with images for brand customization context."""
    products = []
    if not df.empty:
        for _, row in df.head(limit).iterrows():
            product: Dict[str, Any] = {
                "name": row.get("name", "Product"),
                "color": row.get("color", ""),
                "material": row.get("material", ""),
            }
            if "image" in row and pd.notna(row["image"]) and row["image"]:
                product["image"] = row["image"]
            products.append(product)
    return products


# ============================================================================
# FALLBACK ANALYSIS (no LLM — derived from scraped data)
# ============================================================================

def fallback_analysis_data_driven(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame,
) -> Dict[str, Any]:
    colors = extract_colors_from_data(zara_df, uniqlo_df)
    materials = extract_materials_from_data(zara_df, uniqlo_df)
    vibes = infer_vibes_from_products_and_query(query, zara_df, uniqlo_df)
    key_trends = generate_trends_from_data(query, colors, materials, zara_df)

    return {
        "key_trends": key_trends[:5],
        "dominant_palette": colors[:8],
        "materials": materials[:6],
        "aesthetic_vibes": vibes[:4],
        "query": query,
        "market_confidence": "high",
    }


def fallback_brand_customization_ai_driven(
    query: str,
    trend_analysis: Dict,
    zara_products: List[Dict],
    uniqlo_products: List[Dict],
) -> Dict[str, Any]:
    colors = trend_analysis.get("dominant_palette", [])
    materials = trend_analysis.get("materials", [])
    vibes = trend_analysis.get("aesthetic_vibes", [])

    return {
        "old_navy": {
            "summary": f"Accessible {query} with vibrant energy and family appeal. Designed for value-conscious consumers seeking stylish options without premium pricing.",
            "colors": adapt_colors_for_brand(colors, "value"),
            "materials": adapt_materials_for_brand(materials, "budget"),
            "vibes": vibes[:3] + ["accessible"],
            "products": zara_products[:2],
            "target": "Value-conscious families and young adults 18-35",
            "price_positioning": "Accessible entry-level pricing",
        },
        "banana_republic": {
            "summary": f"Elevated {query} crafted from premium materials with refined sophistication. For professionals seeking investment pieces with timeless elegance.",
            "colors": adapt_colors_for_brand(colors, "luxury"),
            "materials": adapt_materials_for_brand(materials, "premium"),
            "vibes": vibes[:3] + ["sophisticated"],
            "products": zara_products[:3],
            "target": "Professional urban adults 30-50 with high disposable income",
            "price_positioning": "Premium positioning with luxury materials",
        },
        "gap": {
            "summary": f"Classic {query} embodying timeless American style. Quality crafted for the modern consumer seeking versatile essentials.",
            "colors": adapt_colors_for_brand(colors, "classic"),
            "materials": adapt_materials_for_brand(materials, "quality"),
            "vibes": vibes[:3] + ["timeless"],
            "products": uniqlo_products[:3],
            "target": "Modern mainstream consumers 25-45",
            "price_positioning": "Mid-range quality and value",
        },
    }


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
        "highlights": trend_terms[:3] if trend_terms else [search_phrase],
        "search_phrase": search_phrase,
    }


# ============================================================================
# UTILITY FUNCTIONS (data-driven extraction)
# ============================================================================

def extract_colors_from_data(zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame) -> List[str]:
    colors: List[str] = []
    for df in [zara_df, uniqlo_df]:
        if not df.empty and "color" in df.columns:
            colors.extend(df["color"].dropna().tolist())

    color_counts: Dict[str, int] = {}
    for color in colors:
        c = str(color).lower().strip()
        if c and c != "nan":
            color_counts[c] = color_counts.get(c, 0) + 1

    result = [c for c, _ in sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:15]]

    if len(result) < 3:
        for default in ["navy", "black", "white"]:
            if default not in result:
                result.append(default)

    return result[:8]


def extract_materials_from_data(zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame) -> List[str]:
    materials: List[str] = []
    for df in [zara_df, uniqlo_df]:
        if not df.empty and "material" in df.columns:
            materials.extend(df["material"].dropna().tolist())

    mat_counts: Dict[str, int] = {}
    for material in materials:
        m = str(material).lower().strip()
        if m and m != "nan":
            mat_counts[m] = mat_counts.get(m, 0) + 1

    result = [m for m, _ in sorted(mat_counts.items(), key=lambda x: x[1], reverse=True)[:15]]

    if len(result) < 3:
        for default in ["cotton", "polyester", "wool blend"]:
            if default not in result:
                result.append(default)

    return result[:6]


def infer_vibes_from_products_and_query(
    query: str,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
) -> List[str]:
    query_lower = query.lower()

    if any(w in query_lower for w in ["denim", "jeans"]):
        vibes = ["casual", "versatile", "classic", "rugged"]
    elif any(w in query_lower for w in ["blazer", "suit", "formal"]):
        vibes = ["professional", "sophisticated", "elegant", "refined"]
    elif any(w in query_lower for w in ["dress", "gown"]):
        vibes = ["elegant", "feminine", "romantic", "graceful"]
    elif any(w in query_lower for w in ["hoodie", "sweatshirt", "casual"]):
        vibes = ["casual", "comfortable", "relaxed", "sporty"]
    else:
        vibes = ["modern", "stylish", "versatile", "contemporary"]

    for df in [zara_df, uniqlo_df]:
        if not df.empty and "name" in df.columns:
            names_text = " ".join(str(n).lower() for n in df["name"].dropna().tolist())
            if ("premium" in names_text or "luxury" in names_text) and "sophisticated" not in vibes:
                vibes.append("sophisticated")
            if "oversized" in names_text and "relaxed" not in vibes:
                vibes.append("relaxed")
            if ("slim" in names_text or "fitted" in names_text) and "tailored" not in vibes:
                vibes.append("tailored")

    return vibes[:4]


def generate_trends_from_data(
    query: str,
    colors: List[str],
    materials: List[str],
    zara_df: pd.DataFrame,
) -> List[str]:
    trends = [f"{query} essentials"]

    if colors:
        trends.append(f"{colors[0]} {query}")
        if len(colors) > 1:
            trends.append(f"{colors[1]} palette")

    if materials:
        trends.append(f"{materials[0]} construction")

    if not zara_df.empty and "name" in zara_df.columns:
        names_text = " ".join(str(n).lower() for n in zara_df["name"].dropna().tolist())
        if "premium" in names_text or "luxury" in names_text:
            trends.append("premium positioning")
        if "versatile" in names_text or "classic" in names_text:
            trends.append("timeless versatility")

    trends.extend([f"modern {query}", f"everyday {query}"])
    return trends[:6]


def adapt_colors_for_brand(base_colors: List[str], brand_type: str) -> List[str]:
    palettes = {
        "value":   ["bright blue", "coral", "red", "white", "navy"],
        "luxury":  ["navy", "black", "charcoal", "camel", "ivory", "burgundy"],
        "classic": ["navy", "white", "grey", "denim blue", "khaki"],
    }
    filler = palettes.get(brand_type, palettes["classic"])
    result = base_colors[:2] if base_colors else []
    for color in filler:
        if color not in result and len(result) < 5:
            result.append(color)
    return result


def adapt_materials_for_brand(base_materials: List[str], brand_type: str) -> List[str]:
    palettes = {
        "budget":  ["polyester", "cotton blend", "nylon", "jersey", "fleece"],
        "premium": ["cashmere", "silk", "merino wool", "premium cotton", "linen"],
        "quality": ["supima cotton", "stretch cotton", "premium denim", "linen blend"],
    }
    filler = palettes.get(brand_type, palettes["quality"])
    take = 1 if brand_type == "budget" else (1 if brand_type == "premium" else 2)
    result = base_materials[:take] if base_materials else []
    for material in filler:
        if material not in result and len(result) < 4:
            result.append(material)
    return result
