"""
LLM Configuration using FREE Groq API
Super fast (100+ tokens/sec) and completely free
"""

import os
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to load from .env file manually if dotenv not available
env_file = Path(".env")
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Groq API Configuration (FREE)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-70b-versatile"  # Free, fast, and accurate

# Model settings
MAX_TOKENS = 2000
TEMPERATURE = 0.7

# Check if API key is configured
USE_FALLBACK = not (GROQ_API_KEY and GROQ_API_KEY.strip())

if USE_FALLBACK:
    print("\n" + "="*60)
    print("⚠️  WARNING: No Groq API key configured")
    print("="*60)
    print("To enable AI-powered analysis:")
    print("1. Visit: https://console.groq.com/keys")
    print("2. Sign up (FREE, no credit card)")
    print("3. Create API key")
    print("4. Add to .env file: GROQ_API_KEY=your-key-here")
    print("\nUsing fallback rule-based analysis for now...")
    print("="*60 + "\n")