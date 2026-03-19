#!/usr/bin/env Rscript

# 04_branches_depth.R  (3D stack-plot version)
# ---------------------------------------------------------------------------
#  • Reads tot_graphrag_d2.csv
#  • Parses reasoning_tree JSON to extract:
#       - branches: count(role == "branch")
#       - max_depth: max(depth)
#       - is_correct: prediction == gold_label
#  • Prints correct/wrong counts overall + per gold_label
#  • Creates THREE 3D scatter plots stacked vertically (YES / MAYBE / NO):
#       x = number of branches
#       y = maximum depth
#       z = stack index for duplicated (x,y) points (shows overlap)
#       color = Correct (green) / Wrong (red)
#  • Saves interactive HTML: 02_03_tot_branch_depth_3d.html
#
# Run:  Rscript 04_branches_depth.R
#
# Requires: readr, dplyr, jsonlite, plotly, htmlwidgets
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(jsonlite)
  library(plotly)
  library(htmlwidgets)
})

csv_file <- "tot_graphrag_d2.csv"
out_html <- "02_03_tot_branch_depth_3d.html"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

# ---- helpers ---------------------------------------------------------------
count_branches <- function(tree_str) {
  if (is.na(tree_str) || !nzchar(tree_str)) return(NA_integer_)
  x <- tryCatch(fromJSON(tree_str), error = function(e) NULL)
  if (is.null(x) || !("role" %in% names(x))) return(NA_integer_)
  sum(tolower(as.character(x$role)) == "branch", na.rm = TRUE)
}

max_tree_depth <- function(tree_str) {
  if (is.na(tree_str) || !nzchar(tree_str)) return(NA_integer_)
  x <- tryCatch(fromJSON(tree_str), error = function(e) NULL)
  if (is.null(x) || !("depth" %in% names(x))) return(NA_integer_)
  suppressWarnings(max(as.integer(x$depth), na.rm = TRUE))
}

# ---- load & tidy -----------------------------------------------------------
raw <- read_csv(csv_file, show_col_types = FALSE)

need_cols <- c("pubmed_id", "prediction", "gold_label", "reasoning_tree")
if (!all(need_cols %in% names(raw))) {
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))
}

df <- raw %>%
  transmute(
    pubmed_id  = as.character(pubmed_id),
    branches   = vapply(reasoning_tree, count_branches, integer(1)),
    max_depth  = vapply(reasoning_tree, max_tree_depth, integer(1)),
    prediction = tolower(trimws(as.character(prediction))),
    gold_label = tolower(trimws(as.character(gold_label))),
    is_correct = prediction == gold_label
  ) %>%
  filter(
    !is.na(branches), branches >= 0,
    !is.na(max_depth), max_depth >= 0,
    gold_label %in% c("yes", "no", "maybe"),
    prediction %in% c("yes", "no", "maybe")
  ) %>%
  mutate(
    status = ifelse(is_correct, "Correct", "Wrong")
  )

if (nrow(df) == 0) stop("No valid rows loaded from CSV after parsing reasoning_tree.")

# ---- print counts (so you can cross-check) ---------------------------------
cat("\n=== Correct vs Wrong counts (overall) ===\n")
overall_tbl <- with(df, table(`Correct Answer` = gold_label, Outcome = status))
print(overall_tbl)

cat("\n=== Totals by outcome (overall) ===\n")
print(with(df, table(Outcome = status)))

cat("\n=== Correct vs Wrong per subplot ===\n")
for (lab in c("yes", "maybe", "no")) {
  sub <- df %>% filter(gold_label == lab)
  cat("\n-- Correct Answer =", toupper(lab), "--\n")
  print(with(sub, table(Outcome = status)))
}

# ---- build z "stack index" to expose overlap --------------------------------
# For each gold_label and each (branches, max_depth) coordinate, assign z=1..k
df <- df %>%
  group_by(gold_label, branches, max_depth) %>%
  arrange(pubmed_id, .by_group = TRUE) %>%
  mutate(z_stack = row_number()) %>%
  ungroup()

# ---- colors -----------------------------------------------------------------
col_map <- c("Correct" = "#4daf4a", "Wrong" = "#e41a1c")

# ---- helper: one 3D plot ----------------------------------------------------
make_3d <- function(gold, show_legend = FALSE) {
  sub <- df %>% filter(gold_label == gold)

  plot_ly(
    data = sub,
    x = ~branches,
    y = ~max_depth,
    z = ~z_stack,
    type = "scatter3d",
    mode = "markers",
    color = ~status,
    colors = col_map,
    marker = list(size = 4, opacity = 0.85),
    text = ~paste0(
      "PMID: ", pubmed_id,
      "<br>Correct Answer: ", toupper(gold_label),
      "<br>Prediction: ", toupper(prediction),
      "<br>Branches: ", branches,
      "<br>Max depth: ", max_depth,
      "<br>Stack z: ", z_stack
    ),
    hoverinfo = "text",
    showlegend = show_legend
  ) %>%
    layout(
      title = list(
        text = paste0("Correct Answer = ", toupper(gold)),
        x = 0.5
      ),
      scene = list(
        xaxis = list(title = "Number of branches"),
        yaxis = list(title = "Maximum depth"),
        zaxis = list(title = "Overlap stack (z)")
      ),
      margin = list(l = 0, r = 0, b = 0, t = 40)
    )
}

p_yes   <- make_3d("yes",   show_legend = TRUE)
p_maybe <- make_3d("maybe", show_legend = FALSE)
p_no    <- make_3d("no",    show_legend = FALSE)

# Stack vertically
combined <- subplot(p_yes, p_maybe, p_no, nrows = 3, shareX = FALSE, shareY = FALSE, titleX = TRUE, titleY = TRUE) %>%
  layout(
    legend = list(orientation = "h", x = 0.35, y = 1.02),
    margin = list(t = 20)
  )

# Save interactive HTML
saveWidget(combined, out_html, selfcontained = TRUE)
cat("\n✅ 3D interactive figure saved to: ", out_html, "\n", sep = "")