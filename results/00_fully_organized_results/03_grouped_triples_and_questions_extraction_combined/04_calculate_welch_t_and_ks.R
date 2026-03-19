#!/usr/bin/env Rscript
# 04_calculate_welch_t_and_ks.R
#
# Welch p-values and KS distances for combined back-validation
# similarities (Triples & Questions), grouped by n_triples,
# vs STS-B bins 2–3, 3–4, 4–5, 5.
#
# Run:
#   Rscript 04_calculate_welch_t_and_ks.R
#
# Inputs (same directory):
#   - combined_from_triples_similarities2.csv
#       columns: paragraph_id, proposition_id, n_triples,
#                triple_combined_similarity, qa_combined_similarity
#   - stsb_miniLM_cosines.csv
#       columns: gold_score, cosine, …
#
# Requires:
#   install.packages(c("readr","dplyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ── file paths ────────────────────────────────────────────────────────────
csv_main <- "combined_from_triples_similarities2.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"
if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

target_bins <- c("2–3","3–4","4–5","5")
row_labels  <- c("1 relationship","2 relationships","3+ relationships")

# ── helper: gold score → bin ─────────────────────────────────────────────
bin_from_gold <- function(g){
  if(!is.finite(g)) return(NA_character_)
  if(g >= 4.999) return("5")
  if(g >= 4)     return("4–5")
  if(g >= 3)     return("3–4")
  if(g >= 2)     return("2–3")
  if(g >= 1)     return("1–2")
  "0–1"
}

# ── load STS-B reference distributions ───────────────────────────────────
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
  transmute(
    bin    = vapply(as.numeric(gold_score), bin_from_gold, character(1)),
    cosine = pmin(pmax(as.numeric(cosine),0),1)
  ) %>%
  filter(bin %in% target_bins, is.finite(cosine))

ref_by_bin <- lapply(setNames(target_bins,target_bins), function(b)
  stsb %>% filter(bin==b) %>% pull(cosine))

# ── load combined similarities & assign relationship groups ──────────────
df <- read_csv(csv_main, show_col_types = FALSE) %>%
  mutate(
    n_triples = as.integer(n_triples),
    triple_combined_similarity = pmin(pmax(as.numeric(triple_combined_similarity),0),1),
    qa_combined_similarity     = pmin(pmax(as.numeric(qa_combined_similarity),0),1),
    rel_group = case_when(
      n_triples <= 1 ~ "1 relationship",
      n_triples == 2 ~ "2 relationships",
      n_triples >= 3 ~ "3+ relationships",
      TRUE ~ NA_character_
    )
  ) %>%
  filter(!is.na(rel_group))

triples_vecs <- lapply(row_labels, function(g)
  df %>% filter(rel_group==g) %>% pull(triple_combined_similarity) %>% (\(x) x[is.finite(x)])())
qa_vecs <- lapply(row_labels, function(g)
  df %>% filter(rel_group==g) %>% pull(qa_combined_similarity) %>% (\(x) x[is.finite(x)])())

# ── statistic helpers ────────────────────────────────────────────────────
welch_p <- function(x,y){
  tryCatch(t.test(x,y)$p.value, error=function(e) NA_real_)
}
ks_D <- function(x,y){
  tryCatch(ks.test(x,y, exact=FALSE)$statistic[[1]], error=function(e) NA_real_)
}

build_matrix <- function(vecs, stat_fun, fmt){
  out <- matrix(NA_character_, nrow=length(row_labels), ncol=length(target_bins),
                dimnames=list(row_labels, target_bins))
  for(i in seq_along(row_labels)){
    for(b in target_bins){
      stat <- stat_fun(vecs[[i]], ref_by_bin[[b]])
      out[i,b] <- fmt(stat)
    }
  }
  out
}

fmt_p  <- function(x) formatC(x, format="e", digits=2)
fmt_D  <- function(x) sprintf("%.4f", x)

P_tri <- build_matrix(triples_vecs, welch_p, fmt_p)
D_tri <- build_matrix(triples_vecs, ks_D,  fmt_D)
P_qa  <- build_matrix(qa_vecs,      welch_p, fmt_p)
D_qa  <- build_matrix(qa_vecs,      ks_D,    fmt_D)

# ── print four tables (no extra text) ─────────────────────────────────────
print(kable(P_tri, caption="Welch p-values (Triples vs STS-B bins)", align="lcccc"))
cat("\n")
print(kable(D_tri, caption="KS distance D (Triples vs STS-B bins)",  align="lcccc"))
cat("\n")
print(kable(P_qa,  caption="Welch p-values (Questions vs STS-B bins)", align="lcccc"))
cat("\n")
print(kable(D_qa,  caption="KS distance D (Questions vs STS-B bins)",  align="lcccc"))