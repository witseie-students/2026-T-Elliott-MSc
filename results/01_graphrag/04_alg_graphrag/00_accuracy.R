#!/usr/bin/env Rscript
# 00_accuracy.R
# ────────────────────────────────────────────────────────────
# Summarise accuracy for each hop-depth in the ALG-GraphRAG
# depth-sweep experiment.  Any file named
#   alg_graphrag_d{N}_qa_outcome.csv
# is automatically included (so depths 1 … 7, or more, are handled).

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr");  need_pkg("stringr")

library(readr);  library(dplyr);  library(stringr)

# ---------- locate result files -----------------------------
pattern <- "^alg_graphrag_d([0-9]+)_qa_outcome\\.csv$"
files   <- list.files(pattern = pattern)

if (length(files) == 0) {
  stop("No alg_graphrag_d*.csv files found in the current directory.")
}

# ---------- aggregate accuracy ------------------------------
summary_df <- lapply(files, function(f) {
  depth <- as.integer(str_match(f, pattern)[, 2])
  df    <- read_csv(f, show_col_types = FALSE)

  if (!all(c("prediction", "gold_label") %in% names(df))) {
    stop(paste0("File ", f, " is missing required columns."))
  }

  acc <- mean(df$prediction == df$gold_label)
  data.frame(depth = depth,
             n_rows = nrow(df),
             accuracy = round(acc * 100, 2),
             file = f,
             stringsAsFactors = FALSE)
}) %>%
  bind_rows() %>%
  arrange(depth)

# ---------- output ------------------------------------------
cat("\nAccuracy by hop-depth\n")
print(
  summary_df %>%
    select(depth, n_rows, accuracy) %>%
    rename(`Depth`   = depth,
           `Rows`    = n_rows,
           `Accuracy (%)` = accuracy)
)

# ---------- save CSV ----------------------------------------
out_name <- "alg_graphrag_depth_accuracy.csv"
write_csv(summary_df, out_name)
cat("\nSaved summary → ", out_name, "\n", sep = "")