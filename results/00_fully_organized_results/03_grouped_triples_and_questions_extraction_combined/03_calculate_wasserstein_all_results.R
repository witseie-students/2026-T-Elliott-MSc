#!/usr/bin/env Rscript
# 08_wasserstein_overall.R
#
# Overall (unstratified) 1–Wasserstein distances between:
#   • triple_combined_similarity (all rows)
#   • qa_combined_similarity     (all rows)
# and STS-B bins: 2–3, 3–4, 4–5, 5
#
# Inputs (same dir):
#   - combined_from_triples_similarities2.csv
#       cols: paragraph_id, proposition_id, n_triples,
#             triple_combined_similarity, qa_combined_similarity
#   - stsb_miniLM_cosines.csv
#       cols: sentence1, sentence2, gold_score, bin, cosine
#
# Output: prints a compact table and a LaTeX table to the console.

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ---- files ---------------------------------------------------------------
csv_main <- "combined_from_triples_similarities2.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ---- load your combined similarities -------------------------------------
df <- read_csv(csv_main, show_col_types = FALSE) %>%
  mutate(
    triple_combined_similarity = pmin(pmax(as.numeric(triple_combined_similarity), 0), 1),
    qa_combined_similarity     = pmin(pmax(as.numeric(qa_combined_similarity), 0), 1)
  )

tri_all <- df %>% filter(!is.na(triple_combined_similarity)) %>% pull(triple_combined_similarity)
qa_all  <- df %>% filter(!is.na(qa_combined_similarity))     %>% pull(qa_combined_similarity)

if (length(tri_all) == 0 && length(qa_all) == 0) {
  stop("No valid triple/QA similarity values found.")
}

# ---- load STS-B; (re)compute bins, ensure 5.0 -> '5' ---------------------
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = pmin(pmax(as.numeric(cosine), 0), 1),
    bin = case_when(
      gold_score >= 4.999 ~ "5",
      gold_score >= 4 & gold_score < 5 ~ "4–5",
      gold_score >= 3 & gold_score < 4 ~ "3–4",
      gold_score >= 2 & gold_score < 3 ~ "2–3",
      gold_score >= 1 & gold_score < 2 ~ "1–2",
      TRUE ~ "0–1"
    )
  )

target_bins <- c("2–3","3–4","4–5","5")
stsb_bins <- stsb %>%
  filter(bin %in% target_bins) %>%
  select(bin, cosine)

# ---- 1-Wasserstein via quantile integral ---------------------------------
w1_quantile <- function(x, y, m = 2000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# ---- compute distances ----------------------------------------------------
compute_row <- function(label, vec) {
  sapply(target_bins, function(b) {
    y <- stsb_bins %>% filter(bin == b) %>% pull(cosine)
    w1_quantile(vec, y, m = 2000)
  })
}

tri_row <- compute_row("Triple back-validation", tri_all)
qa_row  <- compute_row("Question/Answer back-validation", qa_all)

res <- rbind(
  "Triple back-validation"            = tri_row,
  "Question/Answer back-validation"   = qa_row
)

# ---- print compact table --------------------------------------------------
cat("\nOverall 1–Wasserstein distances vs STS-B bins (cosine in [0,1])\n\n")
print(
  kable(
    as.data.frame(res) %>% tibble::rownames_to_column("Distribution") %>%
      mutate(across(-Distribution, ~ round(., 5))),
    align = "lcccc",
    col.names = c("Distribution", "Bin 2–3", "Bin 3–4", "Bin 4–5", "Bin 5")
  )
)

# ---- also print a LaTeX table --------------------------------------------
cat("\n% --- Overall W1 vs STS-B bins (Triples & Q/A) ------------------------\n")
cat("\\begin{table}[H]\n")
cat("  \\centering\n")
cat("  \\caption{Overall 1--Wasserstein distance (W$_1$) between back-validation distributions and STS-B bins.}\n")
cat("  \\label{tab:w1_overall_vs_stsb}\n")
cat("  \\begin{tabular}{@{}lcccc@{}}\n")
cat("    \\toprule\n")
cat("    \\textbf{Distribution} & \\textbf{Bin 2--3} & \\textbf{Bin 3--4} & \\textbf{Bin 4--5} & \\textbf{Bin 5} \\\\\n")
cat("    \\midrule\n")

fmt <- function(x) ifelse(is.finite(x), sprintf("%.5f", x), "")
cat("    \\makecell[l]{Triple back-validation} & ",
    paste(fmt(tri_row), collapse = " & "), " \\\\\n", sep = "")
cat("    \\makecell[l]{Question/Answer back-validation} & ",
    paste(fmt(qa_row), collapse = " & "), " \\\\\n", sep = "")

cat("    \\bottomrule\n")
cat("  \\end{tabular}\n")
cat("\\end{table}\n\n")