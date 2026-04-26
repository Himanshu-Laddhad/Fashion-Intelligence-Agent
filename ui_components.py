"""UI/UX components for Fashion Trend Explorer.

Includes color palettes, aesthetic vibe cards, and confidence badges.
"""

import streamlit as st


# ────────────────────────────────────────────────────────────────────────────
# COLOR SWATCHES & PALETTE
# ────────────────────────────────────────────────────────────────────────────

def render_color_palette(colors: list[str], title: str = "Trend Palette") -> None:
    """Display color swatches from dominant palette."""
    st.subheader(f"🎨 {title}")
    
    if not colors or len(colors) == 0:
        st.caption("No colors available")
        return
    
    cols = st.columns(min(6, len(colors)))
    for idx, color in enumerate(colors[:6]):
        with cols[idx % 6]:
            hex_color = color if color.startswith('#') else f"#{color}"
            st.markdown(f"""
            <div style="
                background-color: {hex_color};
                width: 100%;
                height: 80px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
                display: flex;
                align-items: flex-end;
                justify-content: center;
                padding-bottom: 8px;
                color: white;
                font-weight: bold;
                font-size: 11px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            ">
                {hex_color}
            </div>
            """, unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────────
# AESTHETIC VIBE STYLING
# ────────────────────────────────────────────────────────────────────────────

VIBE_STYLES = {
    "Quiet Luxury": {
        "bg": "#F5F5F5",
        "border": "#D4D4D4",
        "accent": "#999999",
        "text": "#333333",
        "emoji": "✨",
        "description": "Minimalist, understated elegance",
    },
    "Streetwear": {
        "bg": "#1A1A1A",
        "border": "#FF1493",
        "accent": "#00FF00",
        "text": "#FFFFFF",
        "emoji": "🏙️",
        "description": "Bold, edgy urban style",
    },
    "Romantic": {
        "bg": "#FFF0F5",
        "border": "#FFB6C1",
        "accent": "#FF69B4",
        "text": "#8B0000",
        "emoji": "💕",
        "description": "Soft, dreamy, feminine",
    },
    "Utility": {
        "bg": "#2F2F2F",
        "border": "#8B7355",
        "accent": "#D2B48C",
        "text": "#F5F5F5",
        "emoji": "⚙️",
        "description": "Functional, structured, practical",
    },
    "Preppy": {
        "bg": "#FFFAF0",
        "border": "#4169E1",
        "accent": "#FF6347",
        "text": "#000080",
        "emoji": "🎓",
        "description": "Classic, tailored, polished",
    },
    "Boho": {
        "bg": "#FFF8DC",
        "border": "#DAA520",
        "accent": "#CD853F",
        "text": "#8B4513",
        "emoji": "🌿",
        "description": "Free-spirited, earthy, artistic",
    },
}


def render_vibe_card(vibe: str, description: str = "", confidence: float = 0.8) -> None:
    """Render a styled aesthetic vibe card."""
    if vibe not in VIBE_STYLES:
        vibe = "Quiet Luxury"
    
    style = VIBE_STYLES[vibe]
    confidence_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {style['bg']} 0%, rgba(200, 200, 200, 0.1) 100%);
        border: 2px solid {style['border']};
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
    ">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 28px;">{style['emoji']}</span>
            <div>
                <h4 style="margin: 0; color: {style['text']};"><b>{vibe}</b></h4>
                <p style="margin: 3px 0; font-size: 13px; color: {style['accent']};">
                    {description or style['description']}
                </p>
                <div style="font-size: 11px; color: {style['text']}; letter-spacing: 1px;">
                    {confidence_bar} {int(confidence * 100)}%
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_vibe_gallery(vibes: list[str], confidences: dict = None) -> None:
    """Render a gallery of aesthetic vibe cards."""
    st.subheader("🎭 Aesthetic Vibes")
    st.caption("Dominant fashion aesthetics for this trend")
    
    if not vibes:
        st.info("No vibes detected")
        return
    
    confidences = confidences or {}
    
    cols = st.columns(min(2, len(vibes)))
    for idx, vibe in enumerate(vibes[:6]):
        with cols[idx % 2]:
            conf = confidences.get(vibe, 0.75)
            render_vibe_card(vibe, confidence=conf)


# ────────────────────────────────────────────────────────────────────────────
# CONFIDENCE BADGES & GAUGES
# ────────────────────────────────────────────────────────────────────────────

def render_confidence_badge(confidence: float, metric_name: str = "Confidence") -> None:
    """Render an interactive confidence badge (0-1 scale)."""
    pct = int(confidence * 100)
    
    if pct >= 80:
        color = "#2ecc71"  # Green
        label = "High"
    elif pct >= 50:
        color = "#f39c12"  # Orange
        label = "Medium"
    else:
        color = "#e74c3c"  # Red
        label = "Low"
    
    st.markdown(f"""
    <div style="
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(90deg, {color}20 0%, transparent 100%);
        border-left: 4px solid {color};
        border-radius: 8px;
        padding: 15px 20px;
        margin: 8px 0;
    ">
        <div>
            <p style="margin: 0; font-size: 14px; color: #888;">
                {metric_name}
            </p>
            <h3 style="margin: 5px 0; color: {color};">
                {pct}% {label}
            </h3>
        </div>
        <div style="
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: conic-gradient({color} 0deg {pct * 3.6}deg, #ddd {pct * 3.6}deg 360deg);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 24px;
        ">
            {pct}%
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_confidence_row(metrics: dict[str, float]) -> None:
    """Render multiple confidence metrics in a row."""
    st.subheader("📊 Trend Strength Analysis")
    cols = st.columns(len(metrics))
    
    for idx, (name, value) in enumerate(metrics.items()):
        with cols[idx]:
            render_confidence_badge(value, name)
