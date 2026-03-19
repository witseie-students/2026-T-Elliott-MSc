# 01_compare_ordinary.R
# ──────────────────────────────────────────────────────────────
library(tidyverse)

# ---- helper to compute per-class accuracy --------------------
compute_accuracy <- function(df, label) {
  df %>%
    mutate(correct = final_result == actual_result) %>%
    group_by(actual_result) %>%
    summarise(accuracy = mean(correct)) %>%
    mutate(dataset = label)
}

# ---- read both CSVs ------------------------------------------
df_orig <- read_csv("ordinary_rag_qa_outcome.csv",
                    show_col_types = FALSE)
df_noinf <- read_csv("ordinary_rag_qa_outcome_no_inferred.csv",
                     show_col_types = FALSE)

# ---- per-class accuracy --------------------------------------
acc_orig  <- compute_accuracy(df_orig,  "ordinary")
acc_noinf <- compute_accuracy(df_noinf, "no_inferred")

# ---- combine & reshape for comparison ------------------------
comparison_tbl <- bind_rows(acc_orig, acc_noinf) %>%
  pivot_wider(names_from = dataset, values_from = accuracy) %>%
  arrange(match(actual_result, c("yes", "maybe", "no")))

# ---- pretty print --------------------------------------------
cat("\nAccuracy comparison (per class):\n")
comparison_tbl %>%
  mutate(across(-actual_result, ~ scales::percent(.x, accuracy = 0.1))) %>%
  rename(Class = actual_result,
         `Ordinary (all)` = ordinary,
         `Extracted-only` = no_inferred) %>%
  print(n = Inf, width = Inf)

# The tibble is returned invisibly for further use if sourcing the script
invisible(comparison_tbl)