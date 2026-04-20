"""
AI-Powered Fashion Trend Analysis - AI-Driven Color & Material Detection
Using FREE Groq API (Llama 3.1 70B) for intelligent analysis
"""

import pandas as pd
from typing import Dict, List, Any
import json
import asyncio
from groq import Groq
from backend.llm_config import GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS, TEMPERATURE, USE_FALLBACK


# Initialize Groq client (FREE API)
if not USE_FALLBACK:
    client = Groq(api_key=GROQ_API_KEY)
    print("✅ Groq API initialized (FREE LLM)")
else:
    client = None


# ============================================================================
# AI-DRIVEN ANALYSIS FUNCTIONS
# ============================================================================

async def analyze_fashion_data_ai_driven(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    AI-powered analysis with intelligent color and material detection
    Colors and materials extracted from actual data, then validated/enhanced by AI
    """
    
    print("   🤖 Running AI trend analysis with Llama 3.1...")
    
    # Prepare comprehensive data summary
    data_summary = prepare_comprehensive_data_summary(
        query, pinterest_df, zara_df, uniqlo_df, vogue_df
    )
    
    # Use Groq API for intelligent analysis
    if client:
        try:
            analysis = await analyze_with_groq_ai_driven(query, data_summary)
            print("   ✓ AI analysis complete (detected actual market data)")
            return analysis
        except Exception as e:
            print(f"   ⚠️ Groq API error: {e}")
            print("   Falling back to data-driven analysis...")
    
    # Fallback analysis
    return fallback_analysis_data_driven(query, pinterest_df, zara_df, uniqlo_df, vogue_df)


async def customize_for_brands_ai_driven(
    query: str,
    trend_analysis: Dict,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    AI-powered brand customization using detected market data
    Colors and materials come from AI analysis, not hardcoded
    """
    
    print("   🤖 Generating AI-driven brand customizations...")
    
    # Get product examples with images
    zara_products = extract_product_data(zara_df, limit=3)
    uniqlo_products = extract_product_data(uniqlo_df, limit=3)
    
    # Use Groq API for brand customization
    if client:
        try:
            brands = await customize_with_groq_ai_driven(
                query, trend_analysis, zara_products, uniqlo_products
            )
            print("   ✓ Brand customization complete")
            return brands
        except Exception as e:
            print(f"   ⚠️ Groq API error: {e}")
            print("   Falling back to data-driven customization...")
    
    # Fallback customization
    return fallback_brand_customization_ai_driven(
        query, trend_analysis, zara_products, uniqlo_products
    )


# ============================================================================
# GROQ API INTEGRATION - AI-DRIVEN
# ============================================================================

async def analyze_with_groq_ai_driven(query: str, data_summary: Dict) -> Dict[str, Any]:
    """
    Use Groq to intelligently analyze fashion trends from actual scraped data
    Extract colors and materials from real market data
    """
    
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

    def call_groq():
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a fashion trend analyst with access to real market data. Analyze trends scientifically based on actual data. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=1,
            stream=False
        )
        return response.choices[0].message.content
    
    # Execute in thread pool
    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(None, call_groq)
    
    # Parse response
    try:
        response_text = response_text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(line for line in lines if not line.startswith('```'))
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            analysis = json.loads(json_str)
            analysis['query'] = query
            
            # Validate structure
            if not all(key in analysis for key in ['key_trends', 'dominant_palette', 'materials', 'aesthetic_vibes']):
                raise ValueError("Missing required keys in analysis")
            
            return analysis
        else:
            raise ValueError("No JSON found in response")
    
    except Exception as e:
        print(f"   ⚠️ Error parsing Groq response: {e}")
        return fallback_analysis_data_driven(query, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())


async def customize_with_groq_ai_driven(
    query: str,
    trend_analysis: Dict,
    zara_products: List[Dict],
    uniqlo_products: List[Dict]
) -> Dict[str, Any]:
    """
    Use AI to create brand-specific strategies based on DETECTED market trends
    Not hardcoded - everything comes from AI analysis of real data
    """
    
    detected_colors = ", ".join(trend_analysis.get('dominant_palette', [])[:6])
    detected_materials = ", ".join(trend_analysis.get('materials', [])[:6])
    
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

    def call_groq():
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a brand strategy consultant. Create AI-derived strategies based on market data. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS * 2,
            top_p=1,
            stream=False
        )
        return response.choices[0].message.content
    
    # Execute in thread pool
    loop = asyncio.get_event_loop()
    response_text = await loop.run_in_executor(None, call_groq)
    
    try:
        response_text = response_text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(line for line in lines if not line.startswith('```'))
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            brands = json.loads(json_str)
            
            # Validate structure
            required_brands = ['old_navy', 'banana_republic', 'gap']
            if not all(brand in brands for brand in required_brands):
                raise ValueError("Missing required brands in response")
            
            # Add product examples
            if 'old_navy' in brands:
                brands['old_navy']['products'] = zara_products[:2]
            if 'banana_republic' in brands:
                brands['banana_republic']['products'] = zara_products[:3]
            if 'gap' in brands:
                brands['gap']['products'] = uniqlo_products[:3]
            
            return brands
        else:
            raise ValueError("No JSON found in response")
    
    except Exception as e:
        print(f"   ⚠️ Error parsing Groq response: {e}")
        return fallback_brand_customization_ai_driven(query, trend_analysis, zara_products, uniqlo_products)


# ============================================================================
# DATA PREPARATION - COMPREHENSIVE
# ============================================================================

def prepare_comprehensive_data_summary(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Prepare detailed data summary for AI analysis
    Extract ACTUAL colors, materials, and themes from scraped data
    """
    
    colors = []
    materials = []
    product_names = []
    editorial_themes = []
    
    # Extract colors from products
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'color' in df.columns:
            colors.extend(df['color'].dropna().tolist())
    
    # Extract materials from products
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'material' in df.columns:
            materials.extend(df['material'].dropna().tolist())
    
    # Extract product names
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'name' in df.columns:
            product_names.extend(df['name'].dropna().tolist())
    
    # Extract editorial themes
    if not vogue_df.empty:
        if 'title' in vogue_df.columns:
            editorial_themes.extend(vogue_df['title'].dropna().tolist())
        if 'text' in vogue_df.columns:
            editorial_themes.extend(vogue_df['text'].dropna().tolist()[:3])
    
    # Clean and deduplicate
    colors = list(set(str(c).lower().strip() for c in colors if pd.notna(c) and str(c).strip()))[:15]
    materials = list(set(str(m).lower().strip() for m in materials if pd.notna(m) and str(m).strip()))[:15]
    product_names = [str(n) for n in product_names if pd.notna(n)][:10]
    
    return {
        'image_count': len(pinterest_df),
        'zara_count': len(zara_df),
        'uniqlo_count': len(uniqlo_df),
        'vogue_count': len(vogue_df),
        'detected_colors': ', '.join(colors) if colors else 'multiple colors',
        'detected_materials': ', '.join(materials) if materials else 'various materials',
        'product_names': ', '.join(product_names) if product_names else query,
        'editorial_themes': ', '.join([str(t)[:100] for t in editorial_themes[:3]]) if editorial_themes else 'fashion trends'
    }


def extract_product_data(df: pd.DataFrame, limit: int = 3) -> List[Dict]:
    """
    Extract product data with images for visual reference
    """
    
    products = []
    
    if not df.empty:
        for _, row in df.head(limit).iterrows():
            product = {
                'name': row.get('name', 'Product'),
                'color': row.get('color', ''),
                'material': row.get('material', '')
            }
            
            # Include image if available
            if 'image' in row and pd.notna(row['image']) and row['image']:
                product['image'] = row['image']
            
            products.append(product)
    
    return products


# ============================================================================
# FALLBACK ANALYSIS - DATA-DRIVEN
# ============================================================================

def fallback_analysis_data_driven(
    query: str,
    pinterest_df: pd.DataFrame,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame,
    vogue_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Fallback analysis - data-driven without API (uses detected market data)
    """
    
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
        "market_confidence": "high"
    }


def fallback_brand_customization_ai_driven(
    query: str,
    trend_analysis: Dict,
    zara_products: List[Dict],
    uniqlo_products: List[Dict]
) -> Dict[str, Any]:
    """
    Fallback brand customization - data-driven approach
    """
    
    colors = trend_analysis.get("dominant_palette", [])
    materials = trend_analysis.get("materials", [])
    vibes = trend_analysis.get("aesthetic_vibes", [])
    
    return {
        "old_navy": {
            "summary": f"Accessible {query} with vibrant energy and family appeal. Designed for value-conscious consumers seeking stylish options without premium pricing.",
            "colors": adapt_colors_for_brand(colors, 'value'),
            "materials": adapt_materials_for_brand(materials, 'budget'),
            "vibes": vibes[:3] + ["accessible"],
            "products": zara_products[:2],
            "target": "Value-conscious families and young adults 18-35",
            "price_positioning": "Accessible entry-level pricing"
        },
        "banana_republic": {
            "summary": f"Elevated {query} crafted from premium materials with refined sophistication. For professionals seeking investment pieces with timeless elegance.",
            "colors": adapt_colors_for_brand(colors, 'luxury'),
            "materials": adapt_materials_for_brand(materials, 'premium'),
            "vibes": vibes[:3] + ["sophisticated"],
            "products": zara_products[:3],
            "target": "Professional urban adults 30-50 with high disposable income",
            "price_positioning": "Premium positioning with luxury materials"
        },
        "gap": {
            "summary": f"Classic {query} embodying timeless American style. Quality crafted for the modern consumer seeking versatile essentials.",
            "colors": adapt_colors_for_brand(colors, 'classic'),
            "materials": adapt_materials_for_brand(materials, 'quality'),
            "vibes": vibes[:3] + ["timeless"],
            "products": uniqlo_products[:3],
            "target": "Modern mainstream consumers 25-45",
            "price_positioning": "Mid-range quality and value"
        }
    }


# ============================================================================
# UTILITY FUNCTIONS - DATA-DRIVEN
# ============================================================================

def extract_colors_from_data(zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame) -> List[str]:
    """Extract colors from ACTUAL scraped product data"""
    colors = []
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'color' in df.columns:
            colors.extend(df['color'].dropna().tolist())
    
    color_counts = {}
    for color in colors:
        color = str(color).lower().strip()
        if color and color != 'nan':
            color_counts[color] = color_counts.get(color, 0) + 1
    
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
    result = [color for color, _ in sorted_colors[:15]]
    
    # Ensure minimum variety
    if len(result) < 3:
        defaults = ["navy", "black", "white"]
        for default in defaults:
            if default not in result:
                result.append(default)
    
    return result[:8]


def extract_materials_from_data(zara_df: pd.DataFrame, uniqlo_df: pd.DataFrame) -> List[str]:
    """Extract materials from ACTUAL scraped product data"""
    materials = []
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'material' in df.columns:
            materials.extend(df['material'].dropna().tolist())
    
    material_counts = {}
    for material in materials:
        material = str(material).lower().strip()
        if material and material != 'nan':
            material_counts[material] = material_counts.get(material, 0) + 1
    
    sorted_materials = sorted(material_counts.items(), key=lambda x: x[1], reverse=True)
    result = [mat for mat, _ in sorted_materials[:15]]
    
    # Ensure minimum variety
    if len(result) < 3:
        defaults = ["cotton", "polyester", "wool blend"]
        for default in defaults:
            if default not in result:
                result.append(default)
    
    return result[:6]


def infer_vibes_from_products_and_query(
    query: str,
    zara_df: pd.DataFrame,
    uniqlo_df: pd.DataFrame
) -> List[str]:
    """Infer aesthetic vibes from query AND actual product names"""
    vibes = []
    query_lower = query.lower()
    
    # Check query
    if any(word in query_lower for word in ['denim', 'jeans']):
        vibes = ['casual', 'versatile', 'classic', 'rugged']
    elif any(word in query_lower for word in ['blazer', 'suit', 'formal']):
        vibes = ['professional', 'sophisticated', 'elegant', 'refined']
    elif any(word in query_lower for word in ['dress', 'gown']):
        vibes = ['elegant', 'feminine', 'romantic', 'graceful']
    elif any(word in query_lower for word in ['hoodie', 'sweatshirt', 'casual']):
        vibes = ['casual', 'comfortable', 'relaxed', 'sporty']
    else:
        vibes = ['modern', 'stylish', 'versatile', 'contemporary']
    
    # Cross-reference with actual products
    for df in [zara_df, uniqlo_df]:
        if not df.empty and 'name' in df.columns:
            names = df['name'].dropna().tolist()
            names_text = ' '.join([str(n).lower() for n in names])
            
            if 'premium' in names_text or 'luxury' in names_text:
                if 'sophisticated' not in vibes:
                    vibes.append('sophisticated')
            if 'oversized' in names_text:
                if 'relaxed' not in vibes:
                    vibes.append('relaxed')
            if 'slim' in names_text or 'fitted' in names_text:
                if 'tailored' not in vibes:
                    vibes.append('tailored')
    
    return vibes[:4]


def generate_trends_from_data(
    query: str,
    colors: List[str],
    materials: List[str],
    zara_df: pd.DataFrame
) -> List[str]:
    """Generate key trends from actual market data"""
    trends = []
    
    # Primary trend
    trends.append(f"{query} essentials")
    
    # Color-based trend
    if colors:
        trends.append(f"{colors[0]} {query}")
        if len(colors) > 1:
            trends.append(f"{colors[1]} palette")
    
    # Material-based trend
    if materials:
        trends.append(f"{materials[0]} construction")
    
    # From product analysis
    if not zara_df.empty and 'name' in zara_df.columns:
        names = zara_df['name'].dropna().tolist()
        names_text = ' '.join([str(n).lower() for n in names])
        
        if 'premium' in names_text or 'luxury' in names_text:
            trends.append("premium positioning")
        if 'versatile' in names_text or 'classic' in names_text:
            trends.append("timeless versatility")
    
    # Generic fallback
    trends.extend([
        f"modern {query}",
        f"everyday {query}"
    ])
    
    return trends[:6]


def adapt_colors_for_brand(base_colors: List[str], brand_type: str) -> List[str]:
    """
    Adapt detected colors for specific brand positioning
    """
    if brand_type == 'value':
        # Add bright, energetic tones
        bright_palette = ['bright blue', 'coral', 'red', 'white', 'navy']
        result = base_colors[:2] if base_colors else []
        for color in bright_palette:
            if color not in result and len(result) < 5:
                result.append(color)
        return result
    
    elif brand_type == 'luxury':
        # Add sophisticated, refined tones
        luxury_palette = ['navy', 'black', 'charcoal', 'camel', 'ivory', 'burgundy']
        result = base_colors[:2] if base_colors else []
        for color in luxury_palette:
            if color not in result and len(result) < 5:
                result.append(color)
        return result
    
    else:  # classic
        # Stick with classics
        classic_palette = ['navy', 'white', 'grey', 'denim blue', 'khaki']
        result = base_colors[:2] if base_colors else []
        for color in classic_palette:
            if color not in result and len(result) < 5:
                result.append(color)
        return result


def adapt_materials_for_brand(base_materials: List[str], brand_type: str) -> List[str]:
    """
    Adapt detected materials for specific brand positioning
    """
    if brand_type == 'budget':
        budget_materials = ['polyester', 'cotton blend', 'nylon', 'jersey', 'fleece']
        result = base_materials[:1] if base_materials else []
        for material in budget_materials:
            if material not in result and len(result) < 4:
                result.append(material)
        return result
    
    elif brand_type == 'premium':
        premium_materials = ['cashmere', 'silk', 'merino wool', 'premium cotton', 'linen']
        result = base_materials[:1] if base_materials else []
        for material in premium_materials:
            if material not in result and len(result) < 4:
                result.append(material)
        return result
    
    else:  # quality
        quality_materials = ['supima cotton', 'stretch cotton', 'premium denim', 'linen blend']
        result = base_materials[:2] if base_materials else []
        for material in quality_materials:
            if material not in result and len(result) < 4:
                result.append(material)
        return result