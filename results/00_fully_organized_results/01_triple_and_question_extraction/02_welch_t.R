#!/usr/bin/env Rscript
# 03_welch_t.R
#
# Welch t-tests:
#   • Triple back-validated similarities
#   • Answer (question) back-validated similarities
# vs STS-B bins 2–3, 3–4, 4–5, 5
#
# Input files (same folder):
#   - triple_qa_similarities02.csv   (columns: triple_similarity, qa_similarity)
#   - stsb_miniLM_cosines.csv        (columns: gold_score, cosine, …)
#
# Usage:
#   Rscript 03_welch_t.R
#
# Required packages:
#   install.packages(c("readr","dplyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ── file paths ────────────────────────────────────────────────────────────
csv_main <- "triple_qa_similarities02.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ── load back-validation distributions ───────────────────────────────────
df <- read_csv(csv_main, show_col_types = FALSE)

if (!all(c("triple_similarity","qa_similarity") %in% names(df))) {
  stop(csv_main, " must contain columns: triple_similarity, qa_similarity")
}

vec_tri <- df$triple_similarity |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
vec_qa  <- df$qa_similarity     |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()

if (length(vec_tri) == 0 && length(vec_qa) == 0) {
  stop("No valid triple/qa similarity values after cleaning.")
}

# ── load STS-B and recompute bins ─────────────────────────────────────────
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)
if (!all(c("gold_score","cosine") %in% names(stsb_raw))) {
  stop(csv_stsb, " must contain columns: gold_score, cosine")
}

bin_from_gold <- function(g) {
  if (!is.finite(g)) return(NA_character_)
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

stsb <- stsb_raw %>%
  transmute(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin        = vapply(as.numeric(gold_score), bin_from_gold, character(1))
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score), !is.na(bin))

target_bins <- c("2–3","3–4","4–5","5")

# ── Welch t-test helper ──────────────────────────────────────────────────
welch_stats <- function(x, y) {
  tt <- t.test(x, y, var.equal = FALSE, alternative = "two.sided")
  c(t  = unname(tt$statistic),
    df = unname(tt$parameter),
    p  = unname(tt$p.value),
    mx = mean(x),
    my = mean(y))
}

make_row <- function(label, vec, bin_label) {
  ref <- stsb %>% filter(bin == bin_label) %>% pull(cosine)
  stats <- welch_stats(vec, ref)
  tibble(
    Comparison = sprintf("%s vs STS-B (%s)", label, bin_label),
    N_x  = length(vec),
    N_y  = length(ref),
    Mean_x = stats["mx"],
    Mean_y = stats["my"],
    t   = stats["t"],
    df  = stats["df"],
    p   = stats["p"]
  )
}

# ── compute Welch t for each pair ─────────────────────────────────────────
rows <- list()
for (b in target_bins) {
  rows[[length(rows)+1]] <- make_row("Triple back-validation",  vec_tri, b)
  rows[[length(rows)+1]] <- make_row("Answer back-validation",  vec_qa,  b)
}
res <- bind_rows(rows)

# ── formatting ----------------------------------------------------------------
res_fmt <- res %>%
  mutate(
    Mean_x = round(Mean_x, 4),
    Mean_y = round(Mean_y, 4),
    t  = round(as.numeric(t), 3),
    df = round(as.numeric(df), 1),
    p  = formatC(p, format = "e", digits = 3)
  )

# ── print table only ─────────────────────────────────────────────────────
print(kable(res_fmt, align = "lrrrrrrr",
            col.names = c("Comparison","N_x","N_y","Mean_x","Mean_y","t","df","p")))