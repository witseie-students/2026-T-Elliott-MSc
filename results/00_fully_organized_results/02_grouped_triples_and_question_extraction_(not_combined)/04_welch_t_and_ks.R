# 04_welch_t_and_ks.R
#
# Computes Welch t-test p-values and Kolmogorov–Smirnov distances
# for triple and question/answer back-validation similarity distributions
# vs STS-B bins (2–3, 3–4, 4–5, 5), grouped by relationship count (1, 2, 3+).
#
# Usage:
#   Rscript 04_welch_t_and_ks.R
#
# Inputs:
#   - group_1_relationship.csv
#   - group_2_relationships.csv
#   - group_3plus_relationships.csv
#   - stsb_miniLM_cosines.csv

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# --------------------- Configuration -------------------------------------
csv_g1  <- "group_1_relationship.csv"
csv_g2  <- "group_2_relationships.csv"
csv_g3p <- "group_3plus_relationships.csv"
csv_sts <- "stsb_miniLM_cosines.csv"

need_cols_groups <- c("triple_similarity", "qa_similarity")
target_bins <- c("2–3", "3–4", "4–5", "5")
row_labels <- c("1 relationship", "2 relationships", "3+ relationships")

# --------------------- Helper Functions ----------------------------------

bin_from_gold <- function(g) {
  if (!is.finite(g)) return(NA_character_)
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

load_group <- function(path) {
  if (!file.exists(path)) stop("Missing file: ", path)
  df <- read_csv(path, show_col_types = FALSE)
  if (!all(need_cols_groups %in% names(df)))
    stop(basename(path), " must contain: ", paste(need_cols_groups, collapse=", "))
  tri <- df$triple_similarity |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
  qa  <- df$qa_similarity      |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
  list(triple = tri, qa = qa)
}

compute_stats <- function(vec, ref) {
  # Welch t-test
  t_res <- tryCatch(t.test(vec, ref), error = function(e) NA)
  p_val <- if (is.list(t_res)) t_res$p.value else NA_real_
  # KS distance
  ks_res <- tryCatch(ks.test(vec, ref), error = function(e) NA)
  ks_d   <- if (is.list(ks_res)) ks_res$statistic else NA_real_
  list(p = p_val, ks = ks_d)
}

stat_table <- function(vecs, ref_by_bin) {
  result <- lapply(vecs, function(vec) {
    sapply(ref_by_bin, function(ref) compute_stats(vec, ref), simplify = FALSE)
  })

  p_mat <- t(sapply(result, function(r) sapply(r, function(x) formatC(x$p, format="e", digits=2))))
  ks_mat <- t(sapply(result, function(r) sapply(r, function(x) round(x$ks, 4))))
  rownames(p_mat) <- rownames(ks_mat) <- row_labels
  list(p = p_mat, ks = ks_mat)
}

# --------------------- Load Data -----------------------------------------
if (!file.exists(csv_sts)) stop("Missing file: ", csv_sts)
stsb_raw <- read_csv(csv_sts, show_col_types = FALSE)

if (!all(c("gold_score","cosine") %in% names(stsb_raw)))
  stop("stsb_miniLM_cosines.csv must contain columns: gold_score, cosine")

stsb <- stsb_raw %>%
  transmute(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin        = vapply(gold_score, bin_from_gold, character(1))
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score), !is.na(bin))

ref_by_bin <- lapply(setNames(target_bins, target_bins), function(b)
  stsb %>% filter(bin == b) %>% pull(cosine))

g1 <- load_group(csv_g1)
g2 <- load_group(csv_g2)
g3 <- load_group(csv_g3p)

triples_vecs <- list(g1$triple, g2$triple, g3$triple)
qa_vecs      <- list(g1$qa, g2$qa, g3$qa)

# --------------------- Compute and Print ---------------------------------

# Triples
stat_tri <- stat_table(triples_vecs, ref_by_bin)

cat("\nWelch t-test p-values (Triple back-validation vs STS-B bins)\n")
print(kable(stat_tri$p, align = "lcccc"))

cat("\nKolmogorov–Smirnov distances (Triple back-validation vs STS-B bins)\n")
print(kable(stat_tri$ks, align = "lcccc"))

# QA
stat_qa <- stat_table(qa_vecs, ref_by_bin)

cat("\nWelch t-test p-values (Question/Answer back-validation vs STS-B bins)\n")
print(kable(stat_qa$p, align = "lcccc"))

cat("\nKolmogorov–Smirnov distances (Question/Answer back-validation vs STS-B bins)\n")
print(kable(stat_qa$ks, align = "lcccc"))