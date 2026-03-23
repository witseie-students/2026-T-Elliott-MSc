# 013_test_randomness.py
# ════════════════════════════════════════════════════════════════════════════
"""
Monte-Carlo baseline: uniform random guesser on PubMed-QA yes/no/maybe.

For every question in `PUBMED_QA2.csv` the ground-truth label is one of:
  `yes`, `no`, `maybe`.

This management command:
  • runs N_TRIALS independent trials.
  • each trial predicts a label uniformly at random (1/3 each).
  • accumulates an *average* confusion matrix across trials.
  • prints the average accuracy (expected ≈ 33.33%).
  • prints the confusion matrix as expected counts and as row-normalized proportions.
  • prints per-class precision/recall/F1 and overall (weighted) averages.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from statistics import mean

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# ── configuration ───────────────────────────────────────────────────────────
ROOT_DIR = Path(settings.BASE_DIR).parent
DATA_CSV = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"

N_TRIALS = 100000  # dynamic hard-coded value
LABELS = ["yes", "no", "maybe"]  # valid labels in the dataset

# You asked to keep note of these supports; we'll warn if CSV differs.
EXPECTED_SUPPORTS = {"yes": 120, "no": 120, "maybe": 110}

# Display order requested: yes, maybe, no
DISPLAY_ORDER = ["yes", "maybe", "no"]


def safe_div(num: float, den: float) -> float:
    return num / den if den != 0 else 0.0


def compute_prf_from_cm(cm_counts: dict, labels: list[str], supports: dict) -> dict:
    """
    cm_counts[(actual, pred)] = expected count (float)
    labels = list of labels (e.g. ["yes","maybe","no"]) used consistently.
    supports[label] = true count for that label (int)
    Returns per-class precision/recall/f1 and overall weighted averages.
    """
    # Convert to easy access
    # TP for class c: cm[(c,c)]
    # FP for class c: sum_{a!=c} cm[(a,c)]
    # FN for class c: sum_{p!=c} cm[(c,p)]
    per_class = {}
    total = sum(supports[l] for l in labels)

    for c in labels:
        tp = cm_counts[(c, c)]
        fp = sum(cm_counts[(a, c)] for a in labels if a != c)
        fn = sum(cm_counts[(c, p)] for p in labels if p != c)

        prec = safe_div(tp, tp + fp)
        rec = safe_div(tp, tp + fn)
        f1 = safe_div(2 * prec * rec, prec + rec)

        per_class[c] = {"precision": prec, "recall": rec, "f1": f1}

    # Overall weighted by support (true label frequency)
    w_precision = sum(supports[c] * per_class[c]["precision"] for c in labels) / total
    w_recall = sum(supports[c] * per_class[c]["recall"] for c in labels) / total
    w_f1 = sum(supports[c] * per_class[c]["f1"] for c in labels) / total

    # Accuracy from expected counts
    accuracy = sum(cm_counts[(c, c)] for c in labels) / total

    overall = {
        "weighted_precision": w_precision,
        "weighted_recall": w_recall,
        "weighted_f1": w_f1,
        "accuracy": accuracy,
    }

    return {"per_class": per_class, "overall": overall}


def fmt_pct(x: float, dp: int = 2) -> str:
    return f"{100*x:.{dp}f}"


class Command(BaseCommand):
    help = (
        "Run Monte-Carlo simulations where each PubMed-QA question is answered "
        "by a uniform random guess; report average accuracy and expected PRF."
    )

    def handle(self, *args, **opts):
        # 1) load ground-truth labels
        if not DATA_CSV.exists():
            raise CommandError(f"Missing file: {DATA_CSV}")

        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            gold = [row.get("final_decision", "").strip().lower() for row in reader]

        gold = [g for g in gold if g in LABELS]
        total = len(gold)
        if total == 0:
            raise CommandError("No valid final_decision labels found in the CSV.")

        # supports from data
        supports = {lab: 0 for lab in LABELS}
        for g in gold:
            supports[g] += 1

        # sanity check vs expected supports you stated
        if any(supports[k] != EXPECTED_SUPPORTS[k] for k in EXPECTED_SUPPORTS):
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: CSV supports differ from the stated supports "
                    f"(expected {EXPECTED_SUPPORTS}, got {supports}). "
                    "Metrics will be computed using the CSV supports."
                )
            )

        # Use display order yes/maybe/no for printing/tables
        labels = DISPLAY_ORDER
        # Ensure we have supports for all labels in display order
        supports_disp = {lab: supports.get(lab, 0) for lab in labels}

        # 2) run Monte-Carlo trials: track accuracy + accumulate confusion matrix
        accuracies = []
        # accumulate counts across trials (then divide by N_TRIALS to get expected counts)
        cm_sum = {(a, p): 0.0 for a in labels for p in labels}

        for _ in range(N_TRIALS):
            preds = random.choices(LABELS, k=total)  # uniform 1/3 each
            correct = 0

            # update trial confusion counts
            for g, p in zip(gold, preds):
                if g == p:
                    correct += 1
                # only store in our display-order matrix if label is in labels
                # (it will be, because LABELS and labels contain same set)
                cm_sum[(g, p)] += 1.0

            accuracies.append(correct / total)

        avg_acc = mean(accuracies)

        # Expected (mean) confusion matrix counts
        cm_avg = {k: v / N_TRIALS for k, v in cm_sum.items()}

        # 3) Print average accuracy
        self.stdout.write(
            f"Average accuracy over {N_TRIALS} trials: {avg_acc:.2%} "
            "(expected ≈ 33.33%)"
        )

        # 4) Print confusion matrix (expected counts)
        self.stdout.write("\nExpected confusion matrix (counts, averaged over trials):")
        header = "Actual \\ Pred".ljust(14) + "".join([lab.upper().rjust(10) for lab in labels])
        self.stdout.write(header)

        for a in labels:
            row = a.upper().ljust(14)
            for p in labels:
                row += f"{cm_avg[(a, p)]:10.2f}"
            self.stdout.write(row)

        # 5) Print row-normalized confusion matrix (proportions of each actual class)
        self.stdout.write("\nRow-normalized confusion matrix (proportion of each actual class):")
        self.stdout.write(header)

        for a in labels:
            row_total = supports_disp[a]
            row = a.upper().ljust(14)
            for p in labels:
                prop = safe_div(cm_avg[(a, p)], row_total)
                row += f"{fmt_pct(prop, 2).rjust(10)}"
            self.stdout.write(row)

        # 6) Compute PRF from expected confusion matrix
        metrics = compute_prf_from_cm(cm_avg, labels=labels, supports=supports_disp)
        per_class = metrics["per_class"]
        overall = metrics["overall"]

        # 7) Print PRF summary
        self.stdout.write("\nPer-class Precision / Recall / F1 (from expected confusion matrix):")
        self.stdout.write(f"{'Class':<10}{'Precision':>12}{'Recall':>12}{'F1':>12}")
        for c in labels:
            self.stdout.write(
                f"{c.upper():<10}"
                f"{fmt_pct(per_class[c]['precision']):>12}"
                f"{fmt_pct(per_class[c]['recall']):>12}"
                f"{fmt_pct(per_class[c]['f1']):>12}"
            )

        self.stdout.write("\nOverall (weighted by support):")
        self.stdout.write(
            f"Precision: {fmt_pct(overall['weighted_precision'])}% | "
            f"Recall: {fmt_pct(overall['weighted_recall'])}% | "
            f"F1: {fmt_pct(overall['weighted_f1'])}% | "
            f"Accuracy: {fmt_pct(overall['accuracy'])}%"
        )

        # 8) Emit LaTeX table (same style you used)
        self.stdout.write("\nLaTeX table (copy/paste):\n")

        latex = f"""
% --- Monte-Carlo baseline: expected precision / recall / F1 -----------------
\\begin{{table}}[H]
  \\centering
  \\caption{{Per-class precision, recall, and F1-score for the Monte-Carlo uniform random baseline (expected values over trials)}}
  \\label{{tab:mc_random_baseline_prf}}
  \\begin{{tabular}}{{@{{}}lccc@{{}}}}
    \\toprule
    \\textbf{{Class}} & \\textbf{{Precision (\\%)}} & \\textbf{{Recall (\\%)}} & \\textbf{{F1-score (\\%)}} \\\\
    \\midrule
    Yes   & {fmt_pct(per_class["yes"]["precision"])} & {fmt_pct(per_class["yes"]["recall"])} & {fmt_pct(per_class["yes"]["f1"])} \\\\
    Maybe & {fmt_pct(per_class["maybe"]["precision"])} & {fmt_pct(per_class["maybe"]["recall"])} & {fmt_pct(per_class["maybe"]["f1"])} \\\\
    No    & {fmt_pct(per_class["no"]["precision"])} & {fmt_pct(per_class["no"]["recall"])} & {fmt_pct(per_class["no"]["f1"])} \\\\
    \\midrule
    Overall (weighted) & {fmt_pct(overall["weighted_precision"])} & {fmt_pct(overall["weighted_recall"])} & {fmt_pct(overall["weighted_f1"])} \\\\
    \\bottomrule
  \\end{{tabular}}
\\end{{table}}
""".strip()

        self.stdout.write(latex + "\n")