"""
Central configuration for the Tree‑of‑Thought engine.

⚠️  For quick testing you may paste your OpenAI key here,
    but move it to an environment variable (or Django settings)
    before deploying.
"""

from __future__ import annotations
from django.conf import settings

OPENAI_API_KEY: str = settings.OPENAI_API_KEY
MODEL: str = "gpt-4.1-nano"

# Default caps – tweak as needed
MAX_DEPTH: int = 3
MAX_BRANCHES: int = 3
MAX_ANSWERS: int = 8