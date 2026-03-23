"""
Combine evidence sentences into a single answer paragraph
WITHOUT adding external knowledge.
"""

from typing import List, Optional
from openai import OpenAI
from django.conf import settings
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def sentences_to_answer(
    sentences: List[str],
    *,
    question: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> str:
    """
    Turn *sentences* into one coherent paragraph that answers *question*,
    relying ONLY on the provided evidence.

    If sentences are contradictory or clearly insufficient, the assistant
    should respond with:  “Insufficient information.”
    """
    if not sentences:
        raise ValueError("No evidence sentences provided.")

    evidence_block = "\n".join(f"- {s}" for s in sentences)

    system_msg = (
        "You are a question-answering assistant who must craft a single, fluent "
        "paragraph using **only** the evidence sentences provided by the user. "
        "Do NOT add knowledge that isn’t present. If the evidence is insufficient "
        "or contradictory, reply with:  Insufficient information."
    )

    user_msg = (
        (f"Question: {question}\n\n" if question else "")
        + "Evidence sentences:\n"
        + evidence_block
        + "\n\nAnswer in one paragraph:"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"OpenAI error: {exc}")
