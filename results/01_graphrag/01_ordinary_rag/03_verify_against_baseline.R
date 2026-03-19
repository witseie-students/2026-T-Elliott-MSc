#!/usr/bin/env Rscript
# 03_verify_against_baseline.R
# ────────────────────────────────────────────────────────────────────────────
# Compares an ordinary RAG QA run to a baseline-correct subset and reports:
#
# 1) Overall similarity against baseline (percentage)
# 2) Class-wise similarity against baseline (yes / no / maybe)
#    → Of all RAG answers of a given class, how many share PubMed IDs with the
#      baseline-correct set.
# 3) Overall accuracy of the ordinary RAG run (not restricted to baseline)
# 4) Class-wise accuracy of the ordinary RAG run (yes / no / maybe)
#
# Reads:
#   • 01_baseline_correct_only.csv
#       columns: pubmed_id, actual
#   • ordinary_rag_qa_outcome.csv
#       columns: pubmed_id, final_result, actual_result, ...
#
# Prints neatly formatted summaries to stdout.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
})

# ── file paths ──────────────────────────────────────────────────────────────
baseline_file <- "01_baseline_correct_only.csv"
rag_file      <- "ordinary_rag_qa_outcome.csv"

# ── read data ───────────────────────────────────────────────────────────────
baseline <- read_csv(baseline_file, show_col_types = FALSE)
rag      <- read_csv(rag_file,      show_col_types = FALSE)

# ── baseline ID set ─────────────────────────────────────────────────────────
baseline_ids <- baseline %>% select(pubmed_id) %>% distinct()

# ── 1. Overall similarity against baseline ──────────────────────────────────
rag_on_baseline <- rag %>%
  semi_join(baseline_ids, by = "pubmed_id")

overall_similarity_pct <- if (nrow(rag) > 0)
  100 * nrow(rag_on_baseline) / nrow(rag) else NA_real_

# ── 2. Class-wise similarity against baseline ───────────────────────────────
class_similarity <- rag %>%
  mutate(in_baseline = pubmed_id %in% baseline_ids$pubmed_id) %>%
  group_by(final_result) %>%
  summarise(
    total = n(),
    matched_baseline = sum(in_baseline),
    similarity_pct = ifelse(total > 0, 100 * matched_baseline / total, NA_real_),
    .groups = "drop"
  ) %>%
  arrange(final_result)

# ── 3. Overall accuracy (entire RAG set) ────────────────────────────────────
overall_accuracy_pct <- if (nrow(rag) > 0)
  100 * mean(rag$final_result == rag$actual_result) else NA_real_

# ── 4. Class-wise accuracy (entire RAG set) ─────────────────────────────────
class_accuracy <- rag %>%
  mutate(correct = final_result == actual_result) %>%
  group_by(actual_result) %>%
  summarise(
    total = n(),
    correct = sum(correct),
    accuracy_pct = ifelse(total > 0, 100 * correct / total, NA_real_),
    .groups = "drop"
  ) %>%
  arrange(actual_result)

# ── output ──────────────────────────────────────────────────────────────────
cat("\nComparison against baseline:\n")
cat(sprintf("Overall similarity: %.2f%%\n\n", overall_similarity_pct))

cat("Class-wise similarity against baseline:\n")
class_similarity %>%
  select(Class = final_result, Similarity_Percent = similarity_pct) %>%
  mutate(Similarity_Percent = sprintf("%.2f%%", Similarity_Percent)) %>%
  print(n = Inf)

cat("\nActual results (entire dataset, not restricted to baseline):\n")
cat(sprintf("Overall accuracy: %.2f%%\n\n", overall_accuracy_pct))

cat("Class-wise accuracy (entire dataset):\n")
class_accuracy %>%
  select(Class = actual_result, Accuracy_Percent = accuracy_pct) %>%
  mutate(Accuracy_Percent = sprintf("%.2f%%", Accuracy_Percent)) %>%
  print(n = Inf)

cat("\n")