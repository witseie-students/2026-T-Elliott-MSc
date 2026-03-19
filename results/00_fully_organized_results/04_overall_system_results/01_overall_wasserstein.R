#!/usr/bin/env Rscript
# 09_wasserstein_paragraph_overall.R
#
# Overall (paragraph-level) 1–Wasserstein distances between:
#   • recombined_triple_similarity
#   • combined_proposition_similarity
#   • combined_coref_similarity
# and STS-B bins: 2–3, 3–4, 4–5, 5
#
# Inputs (same dir):
#   - combined_paragraph_from_triples.csv
#       cols: paragraph_id,
#             recombined_triple_similarity,
#             combined_proposition_similarity,
#             combined_coref_similarity
#   - stsb_miniLM_cosines.csv
#       cols: sentence1, sentence2, gold_score, bin, cosine
#
# Output: prints a compact table and a LaTeX table to the console.

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ---- files ---------------------------------------------------------------
csv_main <- "combined_paragraph_from_triples.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ---- load paragraph-level distributions ----------------------------------
df <- read_csv(csv_main, show_col_types = FALSE) %>%
  mutate(
    recombined_triple_similarity   = pmin(pmax(as.numeric(recombined_triple_similarity), 0), 1),
    combined_proposition_similarity= pmin(pmax(as.numeric(combined_proposition_similarity), 0), 1),
    combined_coref_similarity      = pmin(pmax(as.numeric(combined_coref_similarity), 0), 1)
  )

tri_all   <- df %>% filter(!is.na(recombined_triple_similarity))    %>% pull(recombined_triple_similarity)
prop_all  <- df %>% filter(!is.na(combined_proposition_similarity)) %>% pull(combined_proposition_similarity)
coref_all <- df %>% filter(!is.na(combined_coref_similarity))       %>% pull(combined_coref_similarity)

if (length(tri_all)==0 && length(prop_all)==0 && length(coref_all)==0) {
  stop("No valid similarity values found in combined_paragraph_from_triples.csv")
}

# ---- load STS-B; recompute bins (ensure 5.0 → '5') ----------------------
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

compute_row <- function(vec) {
  sapply(target_bins, function(b) {
    y <- stsb_bins %>% filter(bin == b) %>% pull(cosine)
    w1_quantile(vec, y, m = 2000)
  })
}

row_tri   <- compute_row(tri_all)
row_prop  <- compute_row(prop_all)
row_coref <- compute_row(coref_all)

res <- rbind(
  "Recombined Triples" = row_tri,
  "Combined Propositions" = row_prop,
  "Combined Coreferences" = row_coref
)

# ---- print compact table --------------------------------------------------
cat("\nParagraph-level overall 1–Wasserstein distances vs STS-B bins (cosine in [0,1])\n\n")
print(
  kable(
    as.data.frame(res) %>% tibble::rownames_to_column("Distribution") %>%
      mutate(across(-Distribution, ~ round(., 5))),
    align = "lcccc",
    col.names = c("Distribution", "Bin 2–3", "Bin 3–4", "Bin 4–5", "Bin 5")
  )
)

# ---- also print a LaTeX table --------------------------------------------
fmt <- function(x) ifelse(is.finite(x), sprintf("%.5f", x), "")
cat("\n% --- Paragraph-level W1 vs STS-B bins ---------------------------------\n")
cat("\\begin{table}[H]\n")
cat("  \\centering\n")
cat("  \\caption{Overall 1--Wasserstein distance (W$_1$) between paragraph-level distributions and STS-B bins.}\n")
cat("  \\label{tab:w1_paragraph_overall_vs_stsb}\n")
cat("  \\begin{tabular}{@{}lcccc@{}}\n")
cat("    \\toprule\n")
cat("    \\textbf{Distribution} & \\textbf{Bin 2--3} & \\textbf{Bin 3--4} & \\textbf{Bin 4--5} & \\textbf{Bin 5} \\\\\n")
cat("    \\midrule\n")
cat("    \\makecell[l]{Recombined Triples} & ",
    paste(fmt(row_tri), collapse = " & "), " \\\\\n", sep = "")
cat("    \\makecell[l]{Combined Propositions} & ",
    paste(fmt(row_prop), collapse = " & "), " \\\\\n", sep = "")
cat("    \\makecell[l]{Combined Coreferences} & ",
    paste(fmt(row_coref), collapse = " & "), " \\\\\n", sep = "")
cat("    \\bottomrule\n")
cat("  \\end{tabular}\n")
cat("\\end{table}\n\n")