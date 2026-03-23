# coreference_agent.py
from __future__ import annotations
from typing import List

from openai import OpenAI
from pydantic import BaseModel, Field
import os

from django.conf import settings

### ----------  Data model ----------

class CoreferenceOutput(BaseModel):
    """Exact schema that the model must return."""
    sentences: List[str] = Field(..., description="Coreference‑resolved sentences")

### ----------  Client setup ----------

# Set up the OpenAI client with your API key

client = OpenAI(api_key=settings.OPENAI_API_KEY)

MODEL_NAME = "gpt-4.1-nano"  

### ----------  Helper ----------

def resolve_coreferences(sentences: List[str]) -> List[str]:
    """
    Expand anaphoric references so every sentence is self‑contained.
    The output list is the same length and order as the input list.
    """
    if not sentences:
        return []

    # Build the user‑visible block (numbered for clarity)
    numbered_block = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))

    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_format={"type": "json_object"},   # strict JSON mode
        messages=[
            # Guard‑rails / schema
            {
                "role": "system",
                "content": (
                    "You are a coreference resolver. "
                    "Coreference resolution means replacing pronouns and other referring expressions—including abbreviations and acronyms—with the explicit entities they denote, so each sentence is self-contained. "
                    "Guidelines:\n"
                    "• Rewrite **each** sentence separately, preserving meaning, tense, and order.\n"
                    "• If an abbreviation (e.g., “UN”) refers to a full name that appears elsewhere (e.g., “United Nations”), replace the abbreviation with the full name, or with “Full Name (ABBR)” if that form helps clarity.\n"
                    "• Do not merge or split sentences or add new information.\n\n"
                    "Return **only** a JSON object that matches this schema exactly:\n"
                    "{\"sentences\": list[str]}\n"
                    "The list must be the same length and order as the input."
                ),
            },

            # Tiny few‑shot
            {
            "role": "assistant",
            "content": (
                "Example input:\n"
                "1. The World Health Organization (WHO) released a report.\n"
                "2. WHO warned that the numbers may rise.\n\n"
                "{\"sentences\": [\n"
                "  \"The World Health Organization (WHO) released a report.\",\n"
                "  \"The World Health Organization (WHO) warned that the numbers may rise.\"\n"
                "]}"
            ),
            },
            
            # Actual user request (fenced for clarity)
            {
                "role": "user",
                "content": f"```text\n{numbered_block}\n```"
            },
        ],
    )

    # Pydantic validation – will raise if model slips
    parsed = CoreferenceOutput.model_validate_json(
        response.choices[0].message.content
    )
    return parsed.sentences
