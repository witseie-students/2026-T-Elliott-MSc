#!/usr/bin/env python3
"""
make_stsb_cosines_dev.py

Create an STS-B cosine CSV from the **validation** split only,
with fixed binning that separates true 5.0 labels into a distinct "5" bin.

Outputs a CSV with columns:
    sentence1, sentence2, gold_score, bin, cosine
where `cosine` is in [0,1].

Requires:
    pip install sentence-transformers datasets numpy
"""

import argparse, csv, sys
import numpy as np
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

def parse_args():
    ap = argparse.ArgumentParser(description="Build STS-B cosine CSV (validation split only) with corrected bins.")
    ap.add_argument("--model",
                    default="sentence-transformers/paraphrase-MiniLM-L6-v2",
                    help="Sentence-Transformers model to use.")
    ap.add_argument("--batch-size", type=int, default=128, help="Encoding batch size (default: 128).")
    ap.add_argument("--out-file", default="stsb_miniLM_cosines.csv", help="Output CSV filename.")
    return ap.parse_args()

def encode_unit_norm(model, texts, batch_size=128):
    """Return L2-normalized embeddings, regardless of sentence-transformers version."""
    try:
        return model.encode(texts, batch_size=batch_size,
                            convert_to_numpy=True, normalize_embeddings=True)
    except TypeError:
        vecs = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

def bin_from_gold(g: float) -> str:
    """Bins based on gold score. Treat 5.0 as a distinct '5' bin."""
    if g is None:
        return None
    try:
        g = float(g)
    except Exception:
        return None
    if g >= 4.999:           # robust 5.0 check
        return "5"
    if 4.0 <= g < 5.0:
        return "4–5"
    if 3.0 <= g < 4.0:
        return "3–4"
    if 2.0 <= g < 3.0:
        return "2–3"
    if 1.0 <= g < 2.0:
        return "1–2"
    return "0–1"

def main():
    args = parse_args()

    # Load **validation** split only (has gold labels)
    print("Loading GLUE STS-B split='validation'…")
    ds = load_dataset("glue", "stsb", split="validation")
    if "label" not in ds.column_names:
        print("Validation split has no 'label'; aborting.", file=sys.stderr)
        sys.exit(1)

    # Extract fields
    sent1 = ds["sentence1"]
    sent2 = ds["sentence2"]
    gold  = np.asarray(ds["label"], dtype=float)   # gold in [0,5]
    print(f"Total labeled rows (validation): {len(ds):,}")

    # Embeddings + cosine
    print(f"Encoding with model: {args.model}")
    model = SentenceTransformer(args.model)
    emb1 = encode_unit_norm(model, sent1, batch_size=args.batch_size)
    emb2 = encode_unit_norm(model, sent2, batch_size=args.batch_size)

    # Cosine: dot product of unit-norm embeddings.
    # Many S-T models produce cosines already in [0,1] in practice.
    cos_raw = np.sum(emb1 * emb2, axis=1)

    # Do NOT remap with (cos+1)/2; just clamp to [0,1] defensively.
    cosine = np.clip(cos_raw, 0.0, 1.0)

    print(f"Cosine stats (raw then clamped): min={cos_raw.min():.4f}, max={cos_raw.max():.4f} "
          f"→ min={cosine.min():.4f}, max={cosine.max():.4f}")

    # Recompute bins (with separate '5')
    bins = [bin_from_gold(g) for g in gold]

    # Quick counts
    from collections import Counter
    counts = Counter(bins)
    print("Counts by bin:", dict(counts))

    # Write CSV
    out = args.out_file
    with open(out, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sentence1", "sentence2", "gold_score", "bin", "cosine"])
        for s1, s2, g, b, c in zip(sent1, sent2, gold, bins, cosine):
            w.writerow([s1, s2, g, b, c])

    print(f"Wrote {len(cosine):,} rows to {out}")

if __name__ == "__main__":
    main()