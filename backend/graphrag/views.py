# backend/graphrag/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .tot.engine import run_tot


class AskQuestionView(APIView):
    """
    POST /api/ask-question/

    Body (JSON)
    -----------
    {
      "text"         : "What is CRISPR and why is it important?",
      "max_depth"    : 5,   # optional – defaults from tot.config
      "max_branches" : 3,   # optional
      "max_answers"  : 5    # optional
    }

    Returns the aggregated answer from the Tree‑of‑Thought engine.
    """

    authentication_classes = []      # re‑enable when ready
    permission_classes = []

    def post(self, request, *args, **kwargs):
        data = request.data
        question = data.get("text")
        if not question:
            return Response(
                {"error": "Missing question text"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse optional overrides — ignore if they aren’t valid ints > 0
        def _as_positive_int(val):
            try:
                iv = int(val)
                return iv if iv > 0 else None
            except (TypeError, ValueError):
                return None

        depth     = _as_positive_int(data.get("max_depth"))
        branches  = _as_positive_int(data.get("max_branches"))
        answers   = _as_positive_int(data.get("max_answers"))

        result = run_tot(
            question,
            max_depth=depth,
            max_branches=branches,
            max_answers=answers,
        )

        return Response(result["aggregate"], status=status.HTTP_200_OK)
