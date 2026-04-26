"""
LLM provider configuration.

Uses Groq API for all AI operations:
  • Groq    — GROQ_API_KEY set in .env              →  llama-3.3-70b-versatile

Call `call_llm(messages, max_tokens)` from anywhere in the codebase.
The function accepts the standard OpenAI-style message list so callers
don't need to know which provider is active.
"""

import os
from pathlib import Path
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

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Groq API key from environmentp()

# ── Provider initialisation ────────────────────────────────────────────────────

_gemini_client: Any = None
_groq_client: Any = None
ACTIVE_PROVIDER: str = "none"

# Try Groq first (preferred)
ifroq_client: Any = None
ACTIVE_PROVIDER: str = "none"

# Initialize Groq
if _GROQ_API_KEY:
    try:
        from groq import Groq

        _groq_client = Groq(api_key=_GROQ_API_KEY)
        ACTIVE_PROVIDER = "groq"
        print(f"✅ Groq AI active ({GROQ_MODEL})")
    except Exception as _e:
        print(f"⚠️  Groq
    print("To enable AI analysis, configure ONE of:")
    print("  • Groq:   add GROQ_API_KEY=<key> to .env")
    print("  • Gemini: place auth.json in the project root")
    print("=" * 60 + "\n")

LLM_AVAILABLE: bool = ACTIVE_PROVIDER != "none"
VISION_AVAILABLE: bool = ACTIVE_PROVIDER == "gemini"


# ── Unified call interfaces ────────────────────────────────────────────────────

def call_llm(messages: list, max_tokens: int = MAX_TOKENS) -> str:
    """
    Synchronous LLM call — provider-agnostic.

    Args:
        messages:   StanGroq AI not configured")
    print("=" * 60)
    print("To enable AI analysis, add to .env:")
    print("  GROQ_API_KEY=<your-groq-api-key>")
    print("=" * 60 + "\n")

LLM_AVAILABLE: bool = ACTIVE_PROVIDER == "groq"
VISION_AVAILABLE: bool = False the call fails.
    """
    if ACTIVE_PROVIDER == "gemini":
        from google.genai.types import GenerateContentConfig

        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        user_parts = [m["content"] for m in messages if m["role"] in ("user", "assistant")]

        config_kwargs: dict = {
            "temperature": TEMPERATURE,
            "max_output_tokens": max_tokens,
        }
        if system_parts:
            config_kwargs["system_instruction"] = "\n".join(system_parts)

        response = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents="\n\n".join(user_parts),
            config=GenerateContentConfig(**config_kwargs),
        )
        return response.text

    if ACTIVE_PROVIDER == "groq":
        response = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=max_tokens,
            top_p=1,
            stream=False,
        )
        return response.choices[0].message.content

    raise RuntimeError(
        "No LLM provider is configured. "
        "Add auth.json (Gemini) or GROQ_API_KEY in .env (Groq)."
    )


def call_llm_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_tokens: int = 200,
) -> str:
    """
    Synchronous multimodal (vision) call — Gemini only.
    Raises RuntimeError when the active provider doesn't support vision.
    """
    if ACTIVE_PROVIDER != "gemini" or _gemini_client is None:
        raise RuntimeError("Vision requires Gemini (auth.json in project root)")

    from google import genai as _genai
    from google.genai.types import GenerateContentConfig

    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            _genai.types.Part(text=prompt),
            _genai.types.Part(
                inline_data=_genai.types.Blob(mime_type=mime_type, data=image_bytes)
            ),
        ],
        config=GenerateContentConfig(temperature=0.1, max_output_tokens=max_tokens),
    )
    return response.text
