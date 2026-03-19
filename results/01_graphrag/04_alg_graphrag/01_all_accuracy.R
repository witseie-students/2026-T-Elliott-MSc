#!/usr/bin/env Rscript
# 01_all_accuracy.R
# ────────────────────────────────────────────────────────────
# For every CSV produced by the depth-sweep experiment
#   alg_graphrag_d{D}_qa_outcome.csv
# compute
#   • P(correct | actual = yes)
#   • P(correct | actual = no)
#   • P(correct | actual = maybe)
#   • overall accuracy
# and write a single summary table.

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr");  need_pkg("tidyr");  need_pkg("stringr")

library(readr);  library(dplyr);  library(tidyr);  library(stringr)

# ---------- locate depth-CSV files --------------------------
files <- list.files(
  pattern = "^alg_graphrag_d[0-9]+_qa_outcome\\.csv$",
  full.names = TRUE
)

if (length(files) == 0)
  stop("No alg_graphrag_d*_qa_outcome.csv files found in the working directory.")

# ---------- helper to process one file ----------------------
process_one <- function(f) {
  depth <- as.integer(str_match(basename(f), "_d([0-9]+)_")[,2])

  df <- read_csv(f, show_col_types = FALSE) |>
          select(gold_label, prediction)

  totals   <- df |> count(gold_label, name = "n_total")
  corrects <- df |> filter(gold_label == prediction) |>
                    count(gold_label, name = "n_correct")

  acc <- totals |>
           left_join(corrects, by = "gold_label") |>
           mutate(n_correct = replace_na(n_correct, 0),
                  acc = n_correct / n_total) |>
           select(gold_label, acc) |>
           pivot_wider(names_from = gold_label,
                       values_from = acc,
                       names_prefix = "acc_")

  overall <- mean(df$gold_label == df$prediction)

  tibble(
    depth      = depth,
    acc_yes    = round(acc$acc_yes*100,   2),
    acc_no     = round(acc$acc_no*100,    2),
    acc_maybe  = round(acc$acc_maybe*100, 2),
    acc_total  = round(overall*100,       2)
  )
}

# ---------- build summary -----------------------------------
summary_tbl <- files |>
                 lapply(process_one) |>
                 bind_rows() |>
                 arrange(depth)

cat("\nAccuracy by hop-depth (per class & total)\n")
print(summary_tbl, n = nrow(summary_tbl))

# ---------- save CSV ----------------------------------------
out_csv <- "alg_graphrag_depth_split_accuracy.csv"
write_csv(summary_tbl, out_csv)
cat("\nSaved summary →", out_csv, "\n")