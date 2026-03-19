# 03_paragraph_level_table.R
# Creates a LaTeX table for paragraph-level back-validation:
# Propositions, Coreferences, Recombined Triples → (Q1, Median, Mean, Q3)

suppressPackageStartupMessages({ library(readr); library(dplyr) })

csv_main <- "combined_paragraph_from_triples.csv"
stopifnot(file.exists(csv_main))

need_cols <- c("paragraph_id",
               "recombined_triple_similarity",
               "combined_proposition_similarity",
               "combined_coref_similarity")

df <- read_csv(csv_main, show_col_types = FALSE)
if (!all(need_cols %in% names(df))) {
  stop("combined_paragraph_from_triples.csv must contain: ",
       paste(need_cols, collapse=", "))
}

# Long form with desired display order
legend_order <- c("Propositions", "Coreferences", "Recombined Triples")

df_long <- bind_rows(
  df %>% transmute(series = "Propositions",
                   value  = as.numeric(combined_proposition_similarity)),
  df %>% transmute(series = "Coreferences",
                   value  = as.numeric(combined_coref_similarity)),
  df %>% transmute(series = "Recombined Triples",
                   value  = as.numeric(recombined_triple_similarity))
) %>%
  filter(!is.na(value)) %>%
  mutate(
    value  = pmin(pmax(value, 0), 1),
    series = factor(series, levels = legend_order, ordered = TRUE)
  )

# Compute stats
stats <- df_long %>%
  group_by(series) %>%
  summarise(
    q1     = quantile(value, 0.25, type = 7, na.rm = TRUE),
    median = median(value, na.rm = TRUE),
    mean   = mean(value, na.rm = TRUE),
    q3     = quantile(value, 0.75, type = 7, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(across(c(q1, median, mean, q3), ~round(.x, 3)))

# Build LaTeX (booktabs)
latex <- c(
  "% --- Paragraph-level back-validation -----------------------------------",
  "\\begin{table}[H]",
  "  \\centering",
  "  \\caption{Paragraph-level cosine-similarity statistics (Q$_1$, Median, Mean, Q$_3$) for combined propositions, combined coreferences, and recombined triples.}",
  "  \\label{tab:paragraph_level_stats}",
  "  \\begin{tabular}{@{}lcccc@{}}",
  "    \\toprule",
  "    \\textbf{Distribution} & \\textbf{Q$_1$ (25\\%)} & \\textbf{Median (50\\%)} & \\textbf{Mean} & \\textbf{Q$_3$ (75\\%)} \\\\",
  "    \\midrule",
  sprintf("    %s & %.3f & %.3f & %.3f & %.3f \\\\",
          stats$series[1], stats$q1[1], stats$median[1], stats$mean[1], stats$q3[1]),
  sprintf("    %s & %.3f & %.3f & %.3f & %.3f \\\\",
          stats$series[2], stats$q1[2], stats$median[2], stats$mean[2], stats$q3[2]),
  sprintf("    %s & %.3f & %.3f & %.3f & %.3f \\\\",
          stats$series[3], stats$q1[3], stats$median[3], stats$mean[3], stats$q3[3]),
  "    \\bottomrule",
  "  \\end{tabular}",
  "\\end{table}"
)

cat(paste(latex, collapse = "\n"), "\n")

# Also save to a .tex file (same folder)
writeLines(latex, "03_paragraph_level_table.tex")
message("Wrote LaTeX table to: 03_paragraph_level_table.tex")