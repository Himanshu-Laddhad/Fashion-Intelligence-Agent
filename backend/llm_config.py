"""
LLM provider configuration.

Uses Groq API for all AI operations:
  • Groq    — GROQ_API_KEY set in .env              →  llama-3.3-70b-versatile

Call `call_llm(messages, max_tokens)` from anywhere in the codebase.
The function accepts the standard OpenAI-style message list so callers
don't need to know which provider is active.
"""

import os
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Shared settings ────────────────────────────────────────────────────────────

TEMPERATURE: float = 0.7
MAX_TOKENS: int = 2000

# ── Provider constants ─────────────────────────────────────────────────────────

# Model names (configurable via environment variables)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Groq API key from environment
_GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()

# ── Provider initialisation ────────────────────────────────────────────────────

_groq_client: Any = None
ACTIVE_PROVIDER: str = "none"

# Initialize Groq
if _GROQ_API_KEY:
    try:
        from groq import Groq

        _groq_client = Groq(api_key=_GROQ_API_KEY)
        ACTIVE_PROVIDER = "groq"
        print(f"✅ Groq AI active ({GROQ_MODEL})")
    except Exception as _e:
        print(f"⚠️  Groq init failed: {_e}")

if ACTIVE_PROVIDER == "none":
    print("\n" + "=" * 60)
    print("⚠️  WARNING: Groq AI not configured")
    print("=" * 60)
    print("To enable AI analysis, add to .env:")
    print("  GROQ_API_KEY=<your-groq-api-key>")
    print("=" * 60 + "\n")

LLM_AVAILABLE: bool = ACTIVE_PROVIDER == "groq"
VISION_AVAILABLE: bool = ACTIVE_PROVIDER == "groq"


# ── Unified call interfaces ────────────────────────────────────────────────────

def call_llm(messages: list, max_tokens: int = MAX_TOKENS) -> str:
    """
    Synchronous LLM call — Groq only.

    Args:
        messages:   Standard chat message list:
                    [{"role": "system"|"user"|"assistant", "content": "..."}]
        max_tokens: Maximum output tokens.

    Returns:
        The model's text response.

    Raises:
        RuntimeError if Groq is not configured or the call fails.
    """
    if ACTIVE_PROVIDER != "groq":
        raise RuntimeError(
            "Groq is not configured. Add GROQ_API_KEY=<key> to .env"
        )

    response = _groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=max_tokens,
        top_p=1,
        stream=False,
    )
    return response.choices[0].message.content


def call_llm_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_tokens: int = 200,
) -> str:
    """
    Multimodal (vision) call — uses Groq's Llama 4 Scout vision model.
    
    Args:
        prompt:     Vision analysis prompt
        image_bytes: Raw image bytes
        mime_type:   Image MIME type (e.g., "image/jpeg")
        max_tokens:  Maximum output tokens
    
    Returns:
        The model's text response analyzing the image.
    
    Raises:
        RuntimeError if Groq is not configured or the call fails.
    """
    import base64
    
    if ACTIVE_PROVIDER != "groq":
        raise RuntimeError(
            "Vision requires Groq to be configured. Add GROQ_API_KEY=<key> to .env"
        )
    
    # Encode image to base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    response = _groq_client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        top_p=1,
        stream=False,
    )
    return response.choices[0].message.content
