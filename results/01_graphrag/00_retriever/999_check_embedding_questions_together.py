#!/usr/bin/env python
# test_additive_embeddings_batch.py
# ---------------------------------------------------------------------
#  Hypothesis:  v(sub-Q1) + v(sub-Q2) [+ v(sub-Q3)]  ≈  v(main-Q)
#
#  For each main question below:
#     • embed main + every sub-question with paraphrase-MiniLM-L6-v2
#     • build a combined vector   v_comb = (v1 + v2 + …) / n   (→ L2-norm)
#     • compare cosine-similarities
#
#  Prints one block per main question.
# ---------------------------------------------------------------------

from __future__ import annotations
from typing import List
import numpy as np
from scipy.spatial.distance import cosine
from sentence_transformers import SentenceTransformer

# ── 1) MINI-DATASET ────────────────────────────────────────────────────
DATA: List[dict] = [
    dict(
        main=(
            "Does daily meditation reduce stress levels and improve "
            "sleep quality in working adults?"
        ),
        subs=[
            "Does daily meditation reduce stress levels in working adults?",
            "Does daily meditation improve sleep quality in working adults?",
        ],
    ),
    dict(
        main=(
            "Can installing rooftop solar panels lower household electricity "
            "bills and decrease carbon emissions over ten years?"
        ),
        subs=[
            "Can installing rooftop solar panels lower household electricity bills?",
            "Can installing rooftop solar panels decrease household carbon emissions over ten years?",
        ],
    ),
    dict(
        main=(
            "Does a plant-based diet help with weight loss, lower cholesterol, "
            "and reduce the risk of type-2 diabetes?"
        ),
        subs=[
            "Does a plant-based diet help with weight loss?",
            "Does a plant-based diet lower cholesterol?",
            "Does a plant-based diet reduce the risk of type-2 diabetes?",
        ],
    ),
    dict(
        main=(
            "Will hybrid work models increase employee satisfaction and "
            "boost productivity in software teams?"
        ),
        subs=[
            "Will hybrid work models increase employee satisfaction in software teams?",
            "Will hybrid work models boost productivity in software teams?",
        ],
    ),
]

# ── 2) HELPERS ─────────────────────────────────────────────────────────
def cos_sim(u: np.ndarray, v: np.ndarray) -> float:
    """Return cosine similarity (1 – cosine distance)."""
    return 1.0 - cosine(u, v) if np.linalg.norm(u) and np.linalg.norm(v) else 0.0


def norm(v: np.ndarray) -> np.ndarray:
    """L2-normalise a vector (safe)."""
    n = np.linalg.norm(v)
    return v / n if n else v


# ── 3) EMBEDDINGS ──────────────────────────────────────────────────────
print("🔧  Loading paraphrase-MiniLM-L6-v2 …")
model = SentenceTransformer("paraphrase-MiniLM-L6-v2")

for item_idx, item in enumerate(DATA, 1):
    main_q = item["main"]
    sub_qs = item["subs"]

    # embed
    v_main  = norm(model.encode(main_q, convert_to_numpy=True))
    v_sub   = [norm(model.encode(q, convert_to_numpy=True)) for q in sub_qs]

    # combine (simple mean of sub-vectors, then L2-norm)
    v_comb  = norm(sum(v_sub) / len(v_sub))

    # similarities
    sims_to_main = [cos_sim(v_main, v) for v in v_sub]
    sim_comb     = cos_sim(v_main, v_comb)

    # ── 4) REPORT ─────────────────────────────────────────────────────
    print(f"\n◼︎ Test #{item_idx}")
    print(f"Main Q   : {main_q}")
    for i, (sq, s) in enumerate(zip(sub_qs, sims_to_main), 1):
        print(f"  Sub-Q{i}: {sq}\n          main ↔ sub{i} : {s: .4f}")
    print(f"  ✚ Combined vector similarity (main ↔ mean(subs)) : {sim_comb: .4f}")

print("\nDone.")