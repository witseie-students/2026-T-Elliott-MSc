"""
graphrag.services
-----------------
Tiny helper that calls the Tree-of-Thought REST endpoint from
anywhere in the backend (management command, celery task, view …)
"""

import os
import requests

# Feel free to move BASE_URL / TOKEN to django-settings if you prefer
BASE_URL = os.getenv("TOT_BASE_URL", "http://127.0.0.1:8000")
TOKEN    = "649ad111031dae78f9fdf80fce9ad07fbeaca812"           # optional

_ENDPOINT = f"{BASE_URL}/api/ask-question/"
_HEADERS  = {"Authorization": f"Token {TOKEN}"} if TOKEN else {}


def ask_question_via_tot(
    question: str,
    *,
    max_depth: int | None = None,
    max_branches: int | None = None,
    max_answers: int | None = None,
) -> str:
    """
    Call `/api/ask-question/` and return the aggregated answer paragraph.

    Raises
    ------
    RuntimeError on HTTP error or malformed JSON.
    """
    payload = {"text": question}

    # only include overrides if provided
    if max_depth:    payload["max_depth"]    = max_depth
    if max_branches: payload["max_branches"] = max_branches
    if max_answers:  payload["max_answers"]  = max_answers

    resp = requests.post(_ENDPOINT, headers=_HEADERS, json=payload, timeout=6000)

    if resp.status_code == 200:
        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError(f"T-o-T response isn’t JSON: {exc}")
    else:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"T-o-T HTTP {resp.status_code}: {detail}")
