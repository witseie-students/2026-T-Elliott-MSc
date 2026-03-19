#!/usr/bin/env Rscript
# 07_wasserstein_from_combined_by_n.R
#
# Computes 1-Wasserstein distances between your combined back-validation
# distributions (by n_triples) and STS-B bins (2–3, 3–4, 4–5, 5),
# and prints two LaTeX tables: Triples and Questions.
#
# Files expected in the working dir:
#   - combined_from_triples_similarities2.csv
#       columns: paragraph_id, proposition_id, n_triples,
#                triple_combined_similarity, qa_combined_similarity
#   - stsb_miniLM_cosines.csv
#       columns: sentence1, sentence2, gold_score, bin, cosine
#
# Run:
#   Rscript 07_wasserstein_from_combined_by_n.R

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr)
})

# ---- config ---------------------------------------------------------------
csv_main <- "combined_from_triples_similarities2.csv"  # change if needed
csv_stsb <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ---- load your combined results ------------------------------------------
df <- read_csv(csv_main, show_col_types = FALSE) %>%
  mutate(
    n_triples = as.integer(n_triples),
    triple_combined_similarity = as.numeric(triple_combined_similarity),
    qa_combined_similarity     = as.numeric(qa_combined_similarity)
  )

# clamp and drop NA
df <- df %>%
  mutate(
    triple_combined_similarity = pmin(pmax(triple_combined_similarity, 0), 1),
    qa_combined_similarity     = pmin(pmax(qa_combined_similarity, 0), 1)
  ) %>%
  filter(!is.na(n_triples))

# group labels: 1, 2, 3+
df <- df %>%
  mutate(
    rel_group = case_when(
      n_triples <= 1 ~ "1 relationship",
      n_triples == 2 ~ "2 relationships",
      n_triples >= 3 ~ "3 or more relationships",
      TRUE ~ NA_character_
    )
  ) %>% filter(!is.na(rel_group))

# ---- load STS-B and (re)compute bins, ensuring true 5.0 -> "5" -----------
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine)
  ) %>%
  filter(!is.na(gold_score), !is.na(cosine)) %>%
  mutate(
    bin = case_when(
      gold_score >= 4.999 ~ "5",
      gold_score >= 4 & gold_score < 5 ~ "4–5",
      gold_score >= 3 & gold_score < 4 ~ "3–4",
      gold_score >= 2 & gold_score < 3 ~ "2–3",
      gold_score >= 1 & gold_score < 2 ~ "1–2",
      TRUE ~ "0–1"
    ),
    cosine = pmin(pmax(cosine, 0), 1)
  )

target_bins <- c("2–3","3–4","4–5","5")
stsb_bins <- stsb %>%
  filter(bin %in% target_bins) %>%
  select(bin, cosine)

# ---- W1 distance via quantile integral -----------------------------------
w1_quantile <- function(x, y, m = 1000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# ---- helper to compute W1 for one column (triples or QA) -----------------
compute_w1_table <- function(df_long, col_name) {
  # df_long has: rel_group, triple_combined_similarity, qa_combined_similarity
  # col_name is one of those two column names
  groups <- c("1 relationship", "2 relationships", "3 or more relationships")
  bins   <- target_bins

  res <- matrix(NA_real_, nrow = length(groups), ncol = length(bins),
                dimnames = list(groups, bins))

  for (g in groups) {
    x <- df_long %>%
      filter(rel_group == g) %>%
      pull({{col_name}}) %>%
      as.numeric()
    x <- x[is.finite(x)]
    if (length(x) == 0) next

    for (b in bins) {
      y <- stsb_bins %>% filter(bin == b) %>% pull(cosine)
      res[g, b] <- w1_quantile(x, y, m = 2000)
    }
  }
  res
}

W_triple <- compute_w1_table(df, triple_combined_similarity)
W_qa     <- compute_w1_table(df, qa_combined_similarity)

# ---- print LaTeX tables ---------------------------------------------------
make_latex_table <- function(W, title, label) {
  # W is a matrix with rownames = groups, colnames = bins
  rnames <- rownames(W)
  cnames <- colnames(W)

  # header
  cat("% --- ", title, " ---\n", sep = "")
  cat("\\begin{table}[H]\n")
  cat("  \\centering\n")
  cat(paste0("  \\caption{", title, "}\n"))
  cat(paste0("  \\label{", label, "}\n"))
  cat("  \\begin{tabular}{@{}l", paste(rep("c", length(cnames)), collapse=""), "@{}}\n")
  cat("    \\toprule\n")
  # column titles (Bin 2--3 etc.)
  bin_titles <- gsub("–", "--", cnames, fixed = TRUE)
  cat("    \\textbf{Distribution} & ",
      paste(paste0("\\textbf{Bin ", bin_titles, "}"), collapse = " & "),
      " \\\\\n")
  cat("    \\midrule\n")

  # rows
  for (r in rnames) {
    vals <- W[r, ]
    nums <- ifelse(is.finite(vals), sprintf("%.4f", vals), "")
    row_label <- switch(r,
                        "1 relationship" = "\\makecell[l]{1 relationship}",
                        "2 relationships" = "\\makecell[l]{2 relationships}",
                        "3 or more relationships" = "\\makecell[l]{3 or more\\\\relationships}",
                        r)
    cat("    ", row_label, " & ", paste(nums, collapse = " & "), " \\\\\n", sep = "")
  }

  cat("    \\bottomrule\n")
  cat("  \\end{tabular}\n")
  cat("\\end{table}\n\n")
}

make_latex_table(
  W_triple,
  "1--Wasserstein distance (W$_1$) between triple back-validation distributions and STS-B bins, stratified by number of relationships extracted.",
  "tab:w1_triples_by_rel_from_combined"
)

make_latex_table(
  W_qa,
  "1--Wasserstein distance (W$_1$) between question/answer back-validation distributions and STS-B bins, stratified by number of relationships extracted.",
  "tab:w1_questions_by_rel_from_combined"
)