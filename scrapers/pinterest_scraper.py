"""
Optimized Pinterest Scraper - 10-12 Images Only
No Unsplash fallback - Pure Pinterest quality
"""

import asyncio
import pandas as pd
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import random


async def scrape_pinterest_optimized(
    query: str,
    output_dir: Path,
    max_images: int = 12
) -> pd.DataFrame:
    """
    Optimized Pinterest scraping using Selenium
    Target: 10-12 high-quality images only
    No Unsplash or fallback sources
    """
    
    try:
        print(f"📌 Searching Pinterest for '{query}' (target: {max_images} images)...")
        
        all_images = []
        
        # ========== PINTEREST SCRAPING ==========
        try:
            # Setup Chrome with optimized settings
            opts = Options()
            opts.add_argument("--headless")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            driver = webdriver.Chrome(options=opts)
            
            # Build search URL
            search_query = query.replace(' ', '+')
            search_url = f"https://www.pinterest.com/search/pins/?q={search_query}&rs=typed&term_meta[]={search_query}%7Ctyped"
            
            print(f"   Accessing Pinterest...")
            driver.get(search_url)
            
            # Initial page load wait
            time.sleep(4)
            
            # Scroll to load images
            scroll_count = 0
            max_scrolls = 6  # Optimize scroll count
            previous_count = 0
            
            while scroll_count < max_scrolls and len(all_images) < max_images * 2:
                # Scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for images to load
                
                # Extract image sources
                img_elements = driver.find_elements(By.TAG_NAME, "img")
                
                for idx, img in enumerate(img_elements):
                    try:
                        src = img.get_attribute("src")
                        
                        # Validate image URL (must be from Pinterest CDN)
                        if (src and "http" in src and 
                            ("pinimg.com" in src or "pinterest.com" in src) and
                            "v1" not in src and  # Skip API/metadata images
                            "static" not in src):  # Skip static assets
                            
                            # Upgrade to higher resolution
                            src = src.replace('/236x/', '/564x/').replace('/474x/', '/564x/')
                            src = src.replace('/200x200_90/', '/564x/')
                            
                            # Get alt text or create description
                            alt = img.get_attribute("alt") or f"{query} fashion inspiration"
                            
                            # Check for duplicates before adding
                            if src not in [img_data['image_url'] for img_data in all_images]:
                                all_images.append({
                                    'image_url': src,
                                    'description': alt,
                                    'source': 'Pinterest',
                                    'pin_id': f'pin_{len(all_images)}',
                                    'link': search_url
                                })
                        
                        if len(all_images) >= max_images * 2:
                            break
                    
                    except Exception as e:
                        continue
                
                # Check if we got new images
                current_count = len(all_images)
                if current_count == previous_count:
                    print(f"   Scroll {scroll_count + 1}: No new images, trying more scrolls...")
                else:
                    print(f"   Scroll {scroll_count + 1}: {current_count} images found")
                
                previous_count = current_count
                scroll_count += 1
                
                # Stop if we have enough
                if len(all_images) >= max_images:
                    break
            
            driver.quit()
            
            # Select best images (max_images)
            final_images = all_images[:max_images]
            print(f"   ✓ Pinterest: {len(final_images)} high-quality images scraped")
        
        except Exception as e:
            print(f"   ⚠️ Pinterest scraping error: {e}")
            if 'driver' in locals():
                try:
                    driver.quit()
                except:
                    pass
            final_images = []
        
        # Create DataFrame
        if final_images:
            df = pd.DataFrame(final_images)
        else:
            print(f"   ⚠️ No Pinterest images found, creating empty DataFrame")
            df = pd.DataFrame()
        
        if not df.empty:
            output_file = output_dir / "pinterest_images.csv"
            df.to_csv(output_file, index=False, encoding="utf-8-sig")
            print(f"✅ Found {len(df)} Pinterest images")
        else:
            print(f"⚠️ No images found for query: {query}")
        
        return df
    
    except Exception as e:
        print(f"❌ Pinterest scraper error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# Test function
if __name__ == "__main__":
    async def test():
        output = Path("output/test")
        output.mkdir(parents=True, exist_ok=True)
        result = await scrape_pinterest_optimized("denim jacket", output, max_images=12)
        print(f"\n✅ Test complete: {len(result)} images")
        if not result.empty:
            print(result.head())
    
    asyncio.run(test())