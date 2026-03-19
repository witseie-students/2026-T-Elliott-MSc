#!/usr/bin/env Rscript
# 03_ks_distance.R
#
# KS distances (two-sample) between
#   • Triple back-validated similarities
#   • Answer back-validated similarities
# and STS-B bins 2–3, 3–4, 4–5, 5
#
# Prints two tables:
#   1. Triple back-validation (D only)
#   2. Answer back-validation (D only)
#
# Inputs:
#   - triple_qa_similarities02.csv
#   - stsb_miniLM_cosines.csv
#
# Required: install.packages(c("readr","dplyr","knitr","tidyr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr); library(tidyr)
})

# ── paths ────────────────────────────────────────────────────────────────
csv_main <- "triple_qa_similarities02.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"
if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ── load back-validated similarities ─────────────────────────────────────
df <- read_csv(csv_main, show_col_types = FALSE)
if (!all(c("triple_similarity","qa_similarity") %in% names(df)))
  stop(csv_main, " must contain columns: triple_similarity, qa_similarity")

vec_tri <- df$triple_similarity |> as.numeric() |> (\(x) pmin(pmax(x,0),1))() |> (\(x) x[is.finite(x)])()
vec_qa  <- df$qa_similarity     |> as.numeric() |> (\(x) pmin(pmax(x,0),1))() |> (\(x) x[is.finite(x)])()

# ── load STS-B and assign bins ───────────────────────────────────────────
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)
if (!all(c("gold_score","cosine") %in% names(stsb_raw)))
  stop(csv_stsb, " must contain columns: gold_score, cosine")

bin_from_gold <- function(g){
  if(!is.finite(g)) return(NA_character_)
  if(g>=4.999) return("5")
  if(g>=4)     return("4–5")
  if(g>=3)     return("3–4")
  if(g>=2)     return("2–3")
  if(g>=1)     return("1–2")
  "0–1"
}

stsb <- stsb_raw %>%
  transmute(
    bin = vapply(as.numeric(gold_score), bin_from_gold, character(1)),
    cosine = pmin(pmax(as.numeric(cosine),0),1)
  ) %>%
  filter(!is.na(bin), is.finite(cosine))

target_bins <- c("2–3","3–4","4–5","5")

# ── KS helper ────────────────────────────────────────────────────────────
ks_D <- function(x,y){
  stats::ks.test(x,y, exact = FALSE)$statistic[[1]]
}

get_Ds <- function(vec,label){
  sapply(target_bins, function(b){
    ref <- stsb %>% filter(bin==b) %>% pull(cosine)
    ks_D(vec,ref)
  })
}

D_tri <- get_Ds(vec_tri,"Triple")
D_qa  <- get_Ds(vec_qa,"Answer")

# ── build wide tables (rounded 4 d.p.) ───────────────────────────────────
tbl_tri <- tibble(
  `Triple back-validation` = round(D_tri,4)
) %>% t() %>% as.data.frame()
colnames(tbl_tri) <- target_bins

tbl_qa <- tibble(
  `Answer back-validation` = round(D_qa,4)
) %>% t() %>% as.data.frame()
colnames(tbl_qa) <- target_bins

# ── print only the two tables ────────────────────────────────────────────
print(kable(tbl_tri, align = "lcccc"))
cat("\n")
print(kable(tbl_qa,  align = "lcccc"))