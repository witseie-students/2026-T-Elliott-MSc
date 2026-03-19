#!/usr/bin/env Rscript
# 99_make_fill_rows.R
# ────────────────────────────────────────────────────────────
# For every PubMed-ID that is present in PUBMED_QA2.csv but
# missing in 00_ordinary_graphrag_qa_outcome.csv, create an
# output row of the form
#
#   pubmed_id,question,long_answer,prediction,gold_label,is_correct
#
# where
#   long_answer = "There is no information to answer the question."
#   prediction  = "maybe"
#   is_correct  = (gold_label == "maybe")

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr")

suppressPackageStartupMessages({
  library(readr);  library(dplyr)
})

# ---------- filenames (expected in working dir) -------------
file_out  <- "00_ordinary_graphrag_qa_outcome.csv"
file_orig <- "PUBMED_QA2.csv"

stopifnot(file.exists(file_out),
          file.exists(file_orig))

# ---------- load data  --------------------------------------
df_out  <- read_csv(file_out,  show_col_types = FALSE) %>%
           mutate(pubmed_id = as.character(pubmed_id))

df_orig <- read_csv(file_orig, show_col_types = FALSE) %>%
           mutate(pubmed_id  = as.character(pubid),
                  gold_label = tolower(final_decision)) %>%
           select(pubmed_id, question, gold_label)

# ---------- find missing IDs --------------------------------
missing_ids <- setdiff(df_orig$pubmed_id, df_out$pubmed_id)
if (length(missing_ids) == 0) {
  cat("✅  No missing rows – nothing to generate.\n")
  quit(save = "no")
}

fill_rows <- df_orig %>%
  filter(pubmed_id %in% missing_ids) %>%
  mutate(
    long_answer = "There is no information to answer the question.",
    prediction  = "maybe",
    is_correct  = (gold_label == "maybe")
  ) %>%
  select(pubmed_id, question, long_answer,
         prediction, gold_label, is_correct)

# ---------- print rows (CSV lines) ---------------------------
cat("Rows to append:\n")
apply(fill_rows, 1, function(r) {
  # quote the long_answer (it contains commas)
  cat(paste0(
    r["pubmed_id" ], ",",
    r["question"  ], ",\"",
    r["long_answer"], "\",",
    r["prediction" ], ",",
    r["gold_label" ], ",",
    ifelse(r["is_correct"], "True", "False"),
    "\n"
  ))
})

# ---------- optional CSV export ------------------------------
write_csv(fill_rows, "rows_to_append.csv")
cat("\nSaved rows → rows_to_append.csv\n")