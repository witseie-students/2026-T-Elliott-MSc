#!/usr/bin/env Rscript
# 05_calculate_welch_t_and_ks_distance_overall_combined.R
#
# Overall Welch p-values and Kolmogorov–Smirnov distances for
# combined back-validation similarities (Triples & Questions)
# versus STS-B bins 2–3, 3–4, 4–5, 5.
#
# Usage:
#   Rscript 05_calculate_welch_t_and_ks_distance_overall_combined.R
#
# Inputs:
#   - combined_from_triples_similarities2.csv
#   - stsb_miniLM_cosines.csv
#
# Required: install.packages(c("readr","dplyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ── files ────────────────────────────────────────────────────────────────
csv_main <- "combined_from_triples_similarities2.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"
if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

target_bins <- c("2–3","3–4","4–5","5")

# ── helper: bin assignment ───────────────────────────────────────────────
bin_from_gold <- function(g){
  if(!is.finite(g)) return(NA_character_)
  if(g>=4.999) return("5")
  if(g>=4)     return("4–5")
  if(g>=3)     return("3–4")
  if(g>=2)     return("2–3")
  if(g>=1)     return("1–2")
  "0–1"
}

# ── load STS-B reference distributions ───────────────────────────────────
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
  transmute(
    bin    = vapply(as.numeric(gold_score), bin_from_gold, character(1)),
    cosine = pmin(pmax(as.numeric(cosine),0),1)
  ) %>%
  filter(bin %in% target_bins, is.finite(cosine))

ref_by_bin <- lapply(setNames(target_bins,target_bins),
                     function(b) stsb %>% filter(bin==b) %>% pull(cosine))

# ── load combined similarities (overall) ─────────────────────────────────
df <- read_csv(csv_main, show_col_types = FALSE) %>%
  mutate(
    triple_combined_similarity = pmin(pmax(as.numeric(triple_combined_similarity),0),1),
    qa_combined_similarity     = pmin(pmax(as.numeric(qa_combined_similarity),0),1)
  )

vec_tri <- df$triple_combined_similarity |> (\(x) x[is.finite(x)])()
vec_qa  <- df$qa_combined_similarity     |> (\(x) x[is.finite(x)])()

# ── statistic helpers ────────────────────────────────────────────────────
welch_p <- function(x,y){
  t.test(x,y)$p.value
}
ks_D <- function(x,y){
  ks.test(x,y, exact=FALSE)$statistic[[1]]
}

# ── build overall table ---------------------------------------------------
make_row <- function(vec, stat_fun, fmt){
  sapply(target_bins, function(b) fmt(stat_fun(vec, ref_by_bin[[b]])))
}

fmt_p <- function(x) formatC(x, format="e", digits=2)
fmt_D <- function(x) sprintf("%.4f", x)

row_names <- c("Welch p-value (Triples)",
               "KS distance D (Triples)",
               "Welch p-value (Questions)",
               "KS distance D (Questions)")

table_mat <- rbind(
  make_row(vec_tri, welch_p, fmt_p),
  make_row(vec_tri, ks_D,   fmt_D),
  make_row(vec_qa,  welch_p, fmt_p),
  make_row(vec_qa,  ks_D,    fmt_D)
)
rownames(table_mat) <- row_names

# ── print single table only ----------------------------------------------
print(kable(table_mat,
            align = "lcccc",
            col.names = c("Bin 2--3","Bin 3--4","Bin 4--5","Bin 5")))