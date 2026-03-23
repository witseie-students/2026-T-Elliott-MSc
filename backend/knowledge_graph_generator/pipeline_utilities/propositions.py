# proposition_agent.py
from __future__ import annotations
from typing import List
import os

from openai import OpenAI
from pydantic import BaseModel, Field

from django.conf import settings

### ----------  Schema ----------

class PropositionOutput(BaseModel):
    """Schema for self‑contained propositional sentences."""
    sentences: List[str] = Field(..., description="Standalone, truth‑apt propositions")

### ----------  Client ----------

# Set up the OpenAI client with your API key
client = OpenAI(api_key=settings.OPENAI_API_KEY)

MODEL_NAME = "gpt-4.1-nano"   # update when a newer model ships

### ----------  Helper ----------

def split_paragraph_into_propositions(paragraph: str) -> List[str]:
    """
    Decompose a paragraph into atomic, self‑contained propositions.
    Each resulting sentence is truth‑apt and retains all context needed
    for stand‑alone interpretation (names, dates, entities fully spelled out).
    """
    if not paragraph.strip():
        return []

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        response_format={"type": "json_object"},   # strict JSON
        messages=[
            # Guard‑rails & schema
            {
                "role": "system",
                "content": (
                    "You are an expert logician and linguist. "
                    "Task: rewrite the user‑provided text as a list of propositions. Propositions are defined as atomic expressions within text, each encapsulating a distinct factoid and presented in a concise, self-contained natural language format."
                    "propositions expressed as clear English sentences.\n\n"
                    "Rules:\n"
                    "•Each output sentence must be **truth‑evaluative** (can be true or false).\n"
                    "•The proposition should not be able to be split into smaller sentences.\n"
                    "•The proposition should contain all the necessary context to stand on its own and interpret what it means independently.\n"
                    "•The must contain a distinct segment of meaning in the text, where the sum of all propositional meanings represents the entire semantic meaning of the text.\n"
                    "•Expand every pronoun, definite NP, or elliptical reference so the sentence is fully self‑contained.\n"
                    "•Preserve tense, modality, dates, and numeric particulars.\n"
                    "•Do **not** add information not present in the source.\n"
                    "•Return **only** a JSON object matching this schema: "
                    "{'sentences': list[str]} in the same order as the source information appears."
                ),
            },
            # Few‑shot miniature example
            {
                "role": "assistant",
                "content": (
                    "Example input:\n"
                    "\"Mary delivered a lecture on AI ethics yesterday. "
                    "It was attended by 200 students. They asked many questions.\"\n\n"
                    "{\"sentences\": [\n"
                    "  \"Mary delivered a lecture on AI ethics yesterday.\",\n"
                    "  \"Two hundred students attended Mary’s lecture on AI ethics yesterday.\",\n"
                    "  \"The students asked many questions during Mary’s lecture on AI ethics yesterday.\"\n"
                    "]}"
                ),
            },
            # Real user paragraph (fenced so numbering is unambiguous)
            {
                "role": "user",
                "content": f"```text\n{paragraph}\n```"
            },
        ],
    )

    parsed = PropositionOutput.model_validate_json(response.choices[0].message.content)
    return parsed.sentences
