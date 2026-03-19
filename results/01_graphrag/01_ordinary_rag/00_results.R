# 00_results.R
# ──────────────────────────────────────────────────────────
# Load tidyverse for convenience; switch to data.table/readr if preferred
library(tidyverse)

# Read the results CSV that lives in the same folder as this script
results <- read_csv("ordinary_rag_qa_outcome.csv",
                    show_col_types = FALSE)  # suppress col-type chatter

# Ensure the columns we need exist
needed <- c("final_result", "actual_result")
stopifnot(all(needed %in% names(results)))

# Summarise correct predictions by class
accuracy_by_class <- results %>%
  mutate(correct = final_result == actual_result) %>%
  group_by(actual_result) %>%
  summarise(correct_count = sum(correct),
            total         = n(),
            accuracy_pct  = round(100 * correct_count / total, 1),
            .groups = "drop")

# Print nicely
cat("\nCorrect predictions by class:\n")
accuracy_by_class %>%
  arrange(desc(actual_result)) %>%          # yes / maybe / no order (optional)
  mutate(label = sprintf("%s:  %d / %d  (%.1f%%)",
                         str_to_title(actual_result), correct_count, total, accuracy_pct)) %>%
  pull(label) %>%
  cat(sep = "\n")

# Optionally, return the tibble for further use
accuracy_by_class