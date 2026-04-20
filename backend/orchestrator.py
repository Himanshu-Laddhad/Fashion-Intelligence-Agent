"""
Fashion Intelligence Orchestrator - AI-Driven Edition
Coordinates all scraping, analysis, and brand customization
AI determines colors and materials instead of hardcoded values
"""

import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import sys
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scrapers.pinterest_scraper import scrape_pinterest_optimized
from scrapers.zara_scraper import scrape_zara
from scrapers.uniqlo_scraper import scrape_uniqlo
from scrapers.vogue_scraper import scrape_vogue
from backend.ai_analyzer import analyze_fashion_data_ai_driven, customize_for_brands_ai_driven


async def run_fashion_query(query: str, output_dir: Path) -> Dict[str, Any]:
    """
    Main orchestration function - runs all scrapers and AI-driven analysis
    AI determines all aesthetic properties instead of hardcoded values
    """
    
    # Validate inputs
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    
    query = query.strip()
    
    if not query:
        raise ValueError("Query cannot be empty")
    
    print(f"\n{'='*60}")
    print(f"🎨 Fashion Intelligence Report: '{query}'")
    print(f"{'='*60}\n")
    
    start_time = datetime.now()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Run all scrapers in parallel (Pinterest limited to 10-12 images)
    print("📊 Step 1: Gathering Data from Multiple Sources...")
    print("-" * 60)
    
    try:
        pinterest_task = scrape_pinterest_optimized(query, output_dir, max_images=12)
        zara_task = scrape_zara(query, output_dir)
        uniqlo_task = scrape_uniqlo(query, output_dir)
        vogue_task = scrape_vogue(query, output_dir)
        
        pinterest_df, zara_df, uniqlo_df, vogue_df = await asyncio.gather(
            pinterest_task,
            zara_task,
            uniqlo_task,
            vogue_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(pinterest_df, Exception):
            print(f"⚠️ Pinterest error: {pinterest_df}")
            pinterest_df = pd.DataFrame()
        
        if isinstance(zara_df, Exception):
            print(f"⚠️ Zara error: {zara_df}")
            zara_df = pd.DataFrame()
        
        if isinstance(uniqlo_df, Exception):
            print(f"⚠️ Uniqlo error: {uniqlo_df}")
            uniqlo_df = pd.DataFrame()
        
        if isinstance(vogue_df, Exception):
            print(f"⚠️ Vogue error: {vogue_df}")
            vogue_df = pd.DataFrame()
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        pinterest_df = pd.DataFrame()
        zara_df = pd.DataFrame()
        uniqlo_df = pd.DataFrame()
        vogue_df = pd.DataFrame()
    
    print("\n" + "-" * 60)
    print("📈 Data Collection Summary:")
    print(f"   Pinterest Images: {len(pinterest_df)}")
    print(f"   Zara Products: {len(zara_df)}")
    print(f"   Uniqlo Products: {len(uniqlo_df)}")
    print(f"   Vogue Articles: {len(vogue_df)}")
    print("-" * 60 + "\n")
    
    # Step 2: Analyze fashion trends with AI-driven color/material detection
    print("🧠 Step 2: AI-Powered Fashion Trend Analysis...")
    print("-" * 60)
    
    trend_analysis = await analyze_fashion_data_ai_driven(
        query=query,
        pinterest_df=pinterest_df,
        zara_df=zara_df,
        uniqlo_df=uniqlo_df,
        vogue_df=vogue_df
    )
    
    print("✅ Trend analysis complete")
    print("-" * 60 + "\n")
    
    # Step 3: AI-driven brand customization with detected colors/materials
    print("🏢 Step 3: Creating Brand-Specific AI Customizations...")
    print("-" * 60)
    
    brand_customizations = await customize_for_brands_ai_driven(
        query=query,
        trend_analysis=trend_analysis,
        zara_df=zara_df,
        uniqlo_df=uniqlo_df
    )
    
    print("✅ Brand customizations complete")
    print("-" * 60 + "\n")
    
    # Step 4: Collect all images for shared visual inspiration (Pinterest only, max 12)
    print("🖼️  Step 4: Organizing Visual Inspiration...")
    
    all_images = []
    
    # Collect images from Pinterest only (10-12 images)
    if not pinterest_df.empty and 'image_url' in pinterest_df.columns:
        pinterest_images = pinterest_df['image_url'].dropna().tolist()
        all_images.extend(pinterest_images)
        print(f"   Added {len(pinterest_images)} Pinterest images")
    
    # Add Zara images as secondary visual reference
    if not zara_df.empty and 'image' in zara_df.columns:
        zara_images = zara_df['image'].dropna().tolist()
        all_images.extend(zara_images[:3])  # Only 3 Zara images
        print(f"   Added {len(zara_images[:3])} Zara product images")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_images = []
    for img in all_images:
        if img and img not in seen and isinstance(img, str) and img.startswith('http'):
            seen.add(img)
            unique_images.append(img)
    
    print(f"   Total unique images: {len(unique_images)}")
    print("-" * 60 + "\n")
    
    # Step 5: Compile final result
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    result = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": duration,
        "images": unique_images[:12],  # Limit to 12 images max
        "trend_analysis": trend_analysis,
        "old_navy": brand_customizations.get("old_navy", {}),
        "banana_republic": brand_customizations.get("banana_republic", {}),
        "gap": brand_customizations.get("gap", {}),
        "data_sources": {
            "pinterest": len(pinterest_df),
            "zara": len(zara_df),
            "uniqlo": len(uniqlo_df),
            "vogue": len(vogue_df)
        },
        "summary": generate_summary(query, trend_analysis)
    }
    
    # Step 6: Save all reports automatically
    save_comprehensive_reports(result, output_dir)
    
    print(f"{'='*60}")
    print(f"✅ Report Complete in {duration:.1f} seconds")
    print(f"{'='*60}\n")
    
    return result


def generate_summary(query: str, trend_analysis: Dict) -> str:
    """Generate executive summary from AI analysis"""
    
    key_trends = trend_analysis.get("key_trends", [])
    dominant_palette = trend_analysis.get("dominant_palette", [])
    aesthetic_vibes = trend_analysis.get("aesthetic_vibes", [])
    materials = trend_analysis.get("materials", [])
    
    trends_text = ", ".join(key_trends[:3]) if key_trends else query
    colors_text = ", ".join(dominant_palette[:3]) if dominant_palette else "neutral tones"
    vibes_text = ", ".join(aesthetic_vibes[:2]) if aesthetic_vibes else "elegant"
    materials_text = ", ".join(materials[:2]) if materials else "premium fabrics"
    
    summary = f"Market analysis reveals '{query}' trending with {trends_text}. "
    summary += f"Dominant palette features {colors_text} with {materials_text}. "
    summary += f"Overall aesthetic: {vibes_text}. "
    summary += f"Each brand interpretation balances AI-detected market trends with signature brand identity."
    
    return summary


def save_comprehensive_reports(result: Dict[str, Any], output_dir: Path):
    """
    Save comprehensive reports automatically to local folder
    """
    
    try:
        print(f"\n{'='*60}")
        print(f"💾 Saving Reports to File...")
        print(f"{'='*60}\n")
        
        # 1. Save full JSON report
        report = {
            "query": result.get("query", ""),
            "timestamp": result.get("timestamp", ""),
            "duration_seconds": result.get("duration_seconds", 0),
            "summary": result.get("summary", ""),
            "data_sources": result.get("data_sources", {}),
            "trend_analysis": result.get("trend_analysis", {}),
            "brands": {
                "old_navy": result.get("old_navy", {}),
                "banana_republic": result.get("banana_republic", {}),
                "gap": result.get("gap", {})
            },
            "visual_inspiration": {
                "total_images": len(result.get("images", [])),
                "image_urls": result.get("images", [])
            }
        }
        
        json_file = output_dir / "full_report.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"   ✓ Saved JSON report: {json_file.name}")
        
        # 2. Save individual brand CSVs
        for brand_name, brand_key in [("Old_Navy", "old_navy"), 
                                       ("Banana_Republic", "banana_republic"), 
                                       ("GAP", "gap")]:
            brand_data = result.get(brand_key, {})
            
            if brand_data and isinstance(brand_data, dict):
                brand_report = {
                    "Brand": brand_name.replace('_', ' '),
                    "Summary": brand_data.get("summary", ""),
                    "Colors": ", ".join([str(c) for c in brand_data.get("colors", [])[:5]]),
                    "Materials": ", ".join([str(m) for m in brand_data.get("materials", [])[:5]]),
                    "Vibes": ", ".join([str(v) for v in brand_data.get("vibes", [])[:3]]),
                    "Target_Audience": brand_data.get("target", "")
                }
                
                brand_df = pd.DataFrame([brand_report])
                csv_file = output_dir / f"{brand_name}_report.csv"
                brand_df.to_csv(csv_file, index=False, encoding="utf-8-sig")
                print(f"   ✓ Saved {brand_name} CSV: {csv_file.name}")
        
        # 3. Save images list
        images = result.get("images", [])
        if images and isinstance(images, list):
            images_df = pd.DataFrame({
                'index': range(len(images)),
                'image_url': images,
                'source': ['Pinterest'] * len(images)
            })
            images_file = output_dir / "visual_inspiration.csv"
            images_df.to_csv(images_file, index=False, encoding="utf-8-sig")
            print(f"   ✓ Saved images list: {images_file.name} ({len(images)} images)")
        
        # 4. Save summary text file
        summary_file = output_dir / "summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Fashion Intelligence Report\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Query: {result.get('query', '')}\n")
            f.write(f"Timestamp: {result.get('timestamp', '')}\n")
            f.write(f"Duration: {result.get('duration_seconds', 0):.1f} seconds\n\n")
            f.write(f"Summary:\n{result.get('summary', '')}\n\n")
            f.write(f"Data Sources:\n")
            for source, count in result.get('data_sources', {}).items():
                f.write(f"  - {source.capitalize()}: {count} items\n")
            f.write(f"\n")
            f.write(f"Trend Analysis:\n")
            trend = result.get('trend_analysis', {})
            f.write(f"  Colors: {', '.join(trend.get('dominant_palette', [])[:5])}\n")
            f.write(f"  Materials: {', '.join(trend.get('materials', [])[:5])}\n")
            f.write(f"  Vibes: {', '.join(trend.get('aesthetic_vibes', [])[:3])}\n")
            f.write(f"  Key Trends: {', '.join(trend.get('key_trends', [])[:5])}\n")
        
        print(f"   ✓ Saved summary: {summary_file.name}")
        
        # 5. Save trend analysis CSV
        trend_data = result.get('trend_analysis', {})
        if trend_data:
            trend_df = pd.DataFrame({
                'Category': ['Colors', 'Materials', 'Vibes', 'Key Trends'],
                'Values': [
                    ', '.join(trend_data.get('dominant_palette', [])[:5]),
                    ', '.join(trend_data.get('materials', [])[:5]),
                    ', '.join(trend_data.get('aesthetic_vibes', [])[:3]),
                    ', '.join(trend_data.get('key_trends', [])[:5])
                ]
            })
            trend_file = output_dir / "trend_analysis.csv"
            trend_df.to_csv(trend_file, index=False, encoding="utf-8-sig")
            print(f"   ✓ Saved trend analysis: {trend_file.name}")
        
        print(f"\n📁 All reports saved to: {output_dir.absolute()}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        print(f"⚠️ Error saving reports: {e}")
        import traceback
        traceback.print_exc()


# For testing
if __name__ == "__main__":
    async def test():
        output = Path("outputs/test")
        result = await run_fashion_query("denim jacket", output)
        print("\n📋 Final Result:")
        print(f"   Images: {len(result.get('images', []))}")
        print(f"   Old Navy colors: {result.get('old_navy', {}).get('colors', [])[:3]}")
        print(f"   Summary: {result.get('summary', '')[:150]}...")
    
    asyncio.run(test())