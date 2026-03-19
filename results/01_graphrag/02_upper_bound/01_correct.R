#!/usr/bin/env Rscript
# 01_correct.r  ─ filter PubMed-QA two-agent results for correct predictions
# ────────────────────────────────────────────────────────────────────────────
# Reads:  00_pubmedqa_two_agent_results.csv
# Writes: 01_pubmedqa_correct_only.csv  (pubmed_id, gold answer)

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
})

# filenames (relative to the script’s directory)
input_file  <- "00_pubmedqa_two_agent_results.csv"
output_file <- "01_pubmedqa_correct_only.csv"

# read, filter, select
read_csv(input_file, show_col_types = FALSE) %>%
  filter(predicted == actual) %>%          # keep only correct rows
  select(pubmed_id, actual) %>%            # keep ID + gold label
  write_csv(output_file)