# tot/self_answer.py

import openai
from . import config  # relative import from tot/config.py

client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

def dummy_answer_question(question: str) -> str:
    """
    Dummy replacement for answer_question that calls ChatGPT directly,
    instructing it to answer clearly and only with factual information.
    """
    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise and reliable assistant. "
                        "Only answer based on information you are certain is true. "
                        "If you are unsure or the answer depends on unknown context, say 'I don't know.' "
                        "Your response should be direct, concise, and factually accurate."
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(Error generating answer: {e})"
