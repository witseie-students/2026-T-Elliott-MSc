# 98_capital.R  (fixed)
library(tidyverse)

csv_file <- "upper_bound_outcome.csv"

valid <- c("yes", "no", "maybe")

df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    predicted = str_to_lower(predicted) %>% str_trim(),
    actual    = str_to_lower(actual)    %>% str_trim()
  ) %>%
  mutate(
    predicted = if_else(predicted %in% valid, predicted, "maybe")  # map weird labels
  )

accuracy <- mean(df$predicted == df$actual)
cat(sprintf("\nOverall accuracy: %.2f%%\n\n", accuracy * 100))

# confusion matrix with totals
cm <- df %>%
  count(actual, predicted) %>%
  pivot_wider(names_from = predicted,
              values_from = n,
              values_fill  = 0) %>%
  arrange(match(actual, valid))

cm <- cm %>%
  mutate(Total = rowSums(across(all_of(valid)))) %>%
  add_row(actual = "Total",
          across(all_of(valid), ~ sum(.)),
          Total = nrow(df))

cat("Confusion matrix (counts):\n")
print(cm, n = Inf, width = Inf)