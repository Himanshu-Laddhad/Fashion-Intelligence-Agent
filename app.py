"""
Streamlit Fashion Intelligence App - Updated UI
Frontend that calls Flask API backend
Text color changes for Zara, Uniqlo, Pinterest, Vogue to black
"""

import streamlit as st
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import io

# Page config
st.set_page_config(
    page_title="Fashion Intelligence Assistant",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - Fixed text color for white backgrounds + Black text for sources
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 2rem;
    }
    .brand-card {
        background: transparent;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
        color: #e0e0e0;
    }
    .summary-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
        color: #e0e0e0;
    }
    .metric-box {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        text-align: center;
    }
    .metric-box h3 {
        color: #000000;
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
    }
    .metric-box p {
        color: #000000;
        margin: 0;
    }
    .trend-pill {
        background: #667eea;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.2rem;
        font-size: 0.85rem;
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 8px;
        transition: transform 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .status-box {
        background: #f0f9ff;
        border-left: 4px solid #0ea5e9;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: #0369a1;
    }
    /* BLACK TEXT for source names */
    .source-name {
        color: #000000 !important;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_BASE_URL = "http://localhost:5000/api"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def call_api(query: str):
    """Call Flask API to analyze fashion query"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            json={"query": query},
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code == 200:
            return response.json().get('data')
        else:
            st.error(f"API Error: {response.json().get('error', 'Unknown error')}")
            return None
    
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API server. Make sure Flask server is running on port 5000")
        st.info("Run: `python server.py` in a separate terminal")
        return None
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None


def display_moodboards(result, message_index=None):
    """Display moodboards with images from Pinterest, Vogue, Zara, Uniqlo"""
    st.markdown("---")
    
    # SHARED VISUAL INSPIRATION SECTION
    st.markdown("### 🎨 Visual Inspiration")
    st.markdown("*Premium imagery from Pinterest*")
    
    # Get all images from result
    all_images = result.get("images", [])
    
    if all_images and isinstance(all_images, list):
        valid_images = [img for img in all_images if img and isinstance(img, str) and img.startswith('http')]
        
        if valid_images:
            # Display in 4-column grid
            cols_per_row = 4
            for i in range(0, min(len(valid_images), 12), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    if i + j < len(valid_images):
                        try:
                            with col:
                                st.image(valid_images[i + j], use_container_width=True)
                        except Exception as e:
                            st.caption("⚠️ Image unavailable")
        else:
            st.info("🖼️ Visual inspiration loading...")
    else:
        st.info("🖼️ No images available for this query")
    
    # BRAND-SPECIFIC ANALYSIS (NO PRICE)
    st.markdown("---")
    st.markdown("### 🏢 Brand-Specific Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    brands = [
        ("Old Navy", "old_navy", col1, "🟦"),
        ("Banana Republic", "banana_republic", col2, "🟫"),
        ("GAP", "gap", col3, "🟨")
    ]
    
    for brand_name, brand_key, col, emoji in brands:
        with col:
            st.markdown(f"#### {emoji} {brand_name}")
            
            brand_data = result.get(brand_key, {})
            
            if not isinstance(brand_data, dict):
                st.warning(f"No data for {brand_name}")
                continue
            
            # Brand summary (NO PRICE)
            summary = brand_data.get("summary", "")
            if summary:
                st.markdown(f'<div class="brand-card">{summary}</div>', 
                           unsafe_allow_html=True)
            
            # Key attributes
            colors = brand_data.get("colors", [])
            if colors and isinstance(colors, list):
                color_text = ', '.join([str(c) for c in colors[:6] if pd.notna(c)])
                if color_text:
                    st.markdown(f"🎨 **Colors:** {color_text}")
            
            materials = brand_data.get("materials", [])
            if materials and isinstance(materials, list):
                material_text = ', '.join([str(m) for m in materials[:5] if pd.notna(m)])
                if material_text:
                    st.markdown(f"🧵 **Materials:** {material_text}")
            
            vibes = brand_data.get("vibes", [])
            if vibes and isinstance(vibes, list):
                vibe_text = ', '.join([str(v) for v in vibes[:4] if pd.notna(v)])
                if vibe_text:
                    st.markdown(f"✨ **Vibes:** {vibe_text}")
            
            # Target audience (NO PRICE)
            target = brand_data.get("target", "")
            if target:
                st.markdown(f"🎯 **Target:** {target}")
            
            # Download button
            button_key = f"download_{brand_key}_{message_index}" if message_index is not None else f"download_{brand_key}_current"
            
            if st.button(f"📥 Download Report", key=button_key, use_container_width=True):
                report_data = {
                    "Brand": brand_name,
                    "Summary": summary,
                    "Colors": ", ".join([str(c) for c in colors[:6] if pd.notna(c)]) if colors else "N/A",
                    "Materials": ", ".join([str(m) for m in materials[:5] if pd.notna(m)]) if materials else "N/A",
                    "Vibes": ", ".join([str(v) for v in vibes[:4] if pd.notna(v)]) if vibes else "N/A",
                    "Target_Audience": target
                }
                
                report_df = pd.DataFrame([report_data])
                csv_buffer = io.StringIO()
                report_df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label=f"💾 Save {brand_name} CSV",
                    data=csv_data,
                    file_name=f"{brand_name.lower().replace(' ', '_')}_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key=f"dl_{button_key}",
                    use_container_width=True
                )

def display_results(result, message_index=None):
    """Display analysis results with moodboards"""
    
    # Summary section
    st.markdown("### 📊 Executive Summary")
    summary = result.get("summary", "Analysis complete")
    st.markdown(f'<div class="summary-card">{summary}</div>', unsafe_allow_html=True)
    
    # Data sources metrics
    col1, col2, col3, col4 = st.columns(4)
    
    sources = result.get("data_sources", {})
    
    with col1:
        st.markdown(f"""
        <div class="metric-box">
        <h3><span class="source-name">📌 Pinterest</span></h3>
        <p style="font-size: 2rem; font-weight: bold; color: #667eea;">{sources.get('pinterest', 0)}</p>
        <p style="color: #0f172a; font-size: 0.85rem;">Images</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-box">
        <h3><span class="source-name">🛍️ Zara</span></h3>
        <p style="font-size: 2rem; font-weight: bold; color: #667eea;">{sources.get('zara', 0)}</p>
        <p style="color: #0f172a; font-size: 0.85rem;">Products</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-box">
        <h3><span class="source-name">👕 Uniqlo</span></h3>
        <p style="font-size: 2rem; font-weight: bold; color: #667eea;">{sources.get('uniqlo', 0)}</p>
        <p style="color: #0f172a; font-size: 0.85rem;">Products</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-box">
        <h3><span class="source-name">📰 Vogue</span></h3>
        <p style="font-size: 2rem; font-weight: bold; color: #667eea;">{sources.get('vogue', 0)}</p>
        <p style="color: #0f172a; font-size: 0.85rem;">Articles</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Trend analysis
    trend_analysis = result.get("trend_analysis", {})
    if trend_analysis:
        st.markdown("### 🎯 Key Trends Identified")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Dominant Palette:**")
            colors = trend_analysis.get("dominant_palette", [])
            if colors:
                color_html = " ".join([f'<span class="trend-pill">{c}</span>' for c in colors[:5]])
                st.markdown(color_html, unsafe_allow_html=True)
            else:
                st.write("No color data available")
        
        with col2:
            st.markdown("**Aesthetic Vibes:**")
            vibes = trend_analysis.get("aesthetic_vibes", [])
            if vibes:
                vibe_html = " ".join([f'<span class="trend-pill">{v}</span>' for v in vibes[:3]])
                st.markdown(vibe_html, unsafe_allow_html=True)
            else:
                st.write("No vibe data available")
        
        st.markdown("**Materials:**")
        materials = trend_analysis.get("materials", [])
        if materials:
            material_html = " ".join([f'<span class="trend-pill">{m}</span>' for m in materials[:5]])
            st.markdown(material_html, unsafe_allow_html=True)
        else:
            st.write("No material data available")
    
    # Display moodboards
    display_moodboards(result, message_index)


# ============================================================================
# MAIN APP
# ============================================================================

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []

# Header
st.markdown('<h1 class="main-header">👗 Fashion Intelligence Assistant</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Real-time analysis from Pinterest, Zara, Uniqlo & Vogue</p>', unsafe_allow_html=True)

# Check API health
try:
    health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
    if health_response.status_code == 200:
        st.success("✅ Backend API Connected")
    else:
        st.warning("⚠️ API health check failed")
except:
    st.error("❌ Backend API not running. Start with: `python server.py`")

# Input section
col1, col2 = st.columns([4, 1])

with col1:
    query = st.text_input(
        "Enter your fashion query:",
        placeholder="e.g., 'denim jacket', 'summer dress', 'oversized hoodie'",
        label_visibility="collapsed"
    )

with col2:
    analyze_button = st.button("🔍 Analyze", use_container_width=True)

# Tip box
st.info("💡 **Tip:** Search for specific items like 'denim jacket', 'summer dress', or 'oversized hoodie' for real product data!")

# Main analysis logic
if analyze_button and query:
    with st.spinner("🚀 Scraping fashion data from multiple sources..."):
        
        # Status updates
        status_container = st.empty()
        
        status_container.markdown("""
        <div class="status-box">
        ⏳ <strong>Scraping in progress...</strong><br>
        • Searching Pinterest for visual inspiration (10-12 images)<br>
        • Fetching Zara products (10 items)<br>
        • Gathering Uniqlo items (10 items)<br>
        • Analyzing Vogue editorial (5 articles)<br>
        • Running AI-powered trend analysis<br>
        • Generating brand-specific insights<br>
        • Saving comprehensive reports
        </div>
        """, unsafe_allow_html=True)
        
        # Call API
        result = call_api(query)
        
        if result:
            # Update status
            output_dir = result.get('output_directory', 'Unknown')
            status_container.success(f"✅ Analysis complete! Reports saved to: `{output_dir}`")
            
            # Add to history
            st.session_state.history.insert(0, {
                'query': query,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'result': result
            })
            
            # Display results
            display_results(result)
        else:
            status_container.error("❌ Analysis failed. Check backend logs.")

elif analyze_button:
    st.warning("⚠️ Please enter a fashion query first!")

# History section
if st.session_state.history:
    st.markdown("---")
    st.subheader("📚 Recent Queries")
    
    for idx, item in enumerate(st.session_state.history[:5]):
        with st.expander(f"🔍 {item['query']} - {item['timestamp']}"):
            display_results(item['result'], message_index=idx)


# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>📊 Real data successfully scraped and AI-analyzed!</p>
    <p style="font-size: 0.85rem;">Powered by Firecrawl + Crawl4AI + Groq AI + Flask Backend</p>
</div>
""", unsafe_allow_html=True)