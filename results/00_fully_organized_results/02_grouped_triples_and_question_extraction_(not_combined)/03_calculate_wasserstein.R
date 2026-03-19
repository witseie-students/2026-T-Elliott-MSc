# 08_w1_by_relcount.R
#
# Compute 1-Wasserstein distances between:
#   • Triple back-validation (triple_similarity)
#   • Question/Answer back-validation (qa_similarity)
# for each relationship group (1, 2, 3+), against STS-B bins {2–3, 3–4, 4–5, 5}.
#
# Usage:
#   Rscript 08_w1_by_relcount.R
#
# Inputs (same folder):
#   - group_1_relationship.csv
#   - group_2_relationships.csv
#   - group_3plus_relationships.csv
#       (columns: paragraph_id, proposition_id, quad_index,
#                 triple_similarity, qa_similarity, n_relationships)
#   - stsb_miniLM_cosines.csv
#       (columns: sentence1, sentence2, gold_score, bin, cosine)

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(knitr)
})

# ---- files ---------------------------------------------------------------
csv_g1  <- "group_1_relationship.csv"
csv_g2  <- "group_2_relationships.csv"
csv_g3p <- "group_3plus_relationships.csv"
csv_sts <- "stsb_miniLM_cosines.csv"

need_cols_groups <- c("triple_similarity","qa_similarity")
target_bins <- c("2–3","3–4","4–5","5")

# ---- helpers -------------------------------------------------------------
# 1-Wasserstein (Earth-Mover) via quantile integral approximation:
# W1(F,G) = ∫_0^1 |F^{-1}(t) − G^{-1}(t)| dt  ≈ mean over a dense prob grid
w1_quantile <- function(x, y, m = 2000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# Re-bin from gold_score to ensure a distinct "5" bin for true 5.0s
bin_from_gold <- function(g) {
  if (!is.finite(g)) return(NA_character_)
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

# Load a group file and return cleaned vectors
load_group <- function(path) {
  if (!file.exists(path)) stop("Missing file: ", path)
  df <- read_csv(path, show_col_types = FALSE)
  if (!all(need_cols_groups %in% names(df)))
    stop(basename(path), " must contain: ", paste(need_cols_groups, collapse=", "))
  tri <- df$triple_similarity |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
  qa  <- df$qa_similarity      |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
  list(triple = tri, qa = qa)
}

# ---- load STS-B and split by bins ---------------------------------------
if (!file.exists(csv_sts)) stop("Missing file: ", csv_sts)
stsb_raw <- read_csv(csv_sts, show_col_types = FALSE)

if (!all(c("gold_score","cosine") %in% names(stsb_raw)))
  stop("stsb_miniLM_cosines.csv must contain columns: gold_score, cosine")

stsb <- stsb_raw %>%
  transmute(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin        = vapply(as.numeric(gold_score), bin_from_gold, character(1))
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score), !is.na(bin))

# Make a named list of reference vectors per target bin
ref_by_bin <- lapply(setNames(target_bins, target_bins), function(b)
  stsb %>% filter(bin == b) %>% pull(cosine))

# ---- load group distributions -------------------------------------------
g1  <- load_group(csv_g1)
g2  <- load_group(csv_g2)
g3p <- load_group(csv_g3p)

# Relationship labels for rows
row_labels <- c("1 relationship", "2 relationships", "3+ relationships")

# ---- compute W1 tables ---------------------------------------------------
compute_w1_row <- function(vec, refs) {
  sapply(refs, function(ref) w1_quantile(vec, ref), simplify = TRUE, USE.NAMES = TRUE)
}

# Triples
W1_triples <- rbind(
  compute_w1_row(g1$triple,  ref_by_bin),
  compute_w1_row(g2$triple,  ref_by_bin),
  compute_w1_row(g3p$triple, ref_by_bin)
)
rownames(W1_triples) <- row_labels

# Questions
W1_questions <- rbind(
  compute_w1_row(g1$qa,  ref_by_bin),
  compute_w1_row(g2$qa,  ref_by_bin),
  compute_w1_row(g3p$qa, ref_by_bin)
)
rownames(W1_questions) <- row_labels

# ---- print neat wide tables ---------------------------------------------
cat("\n1-Wasserstein distances (Triple back-validation vs STS-B bins)\n")
tbl_tri <- as.data.frame(W1_triples) %>%
  mutate(`Number of Relationships` = rownames(W1_triples)) %>%
  relocate(`Number of Relationships`) %>%
  mutate(across(all_of(target_bins), ~round(., 5)))
print(kable(tbl_tri, align = "lcccc"))

cat("\n1-Wasserstein distances (Question/Answer back-validation vs STS-B bins)\n")
tbl_qa <- as.data.frame(W1_questions) %>%
  mutate(`Number of Relationships` = rownames(W1_questions)) %>%
  relocate(`Number of Relationships`) %>%
  mutate(across(all_of(target_bins), ~round(., 5)))
print(kable(tbl_qa, align = "lcccc"))

# Optional: quick Ns per group (sanity check)
cat("\nCounts (n) per group:\n")
n_df <- tibble(
  `Number of Relationships` = row_labels,
  n_triple = c(length(g1$triple), length(g2$triple), length(g3p$triple)),
  n_qa     = c(length(g1$qa),     length(g2$qa),     length(g3p$qa))
)
print(kable(n_df, align = "lcc"))