#!/usr/bin/env Rscript

# 03_loops_tot.R
# ---------------------------------------------------------------------------
#  • Reads tot_graphrag_d2.csv
#  • Extracts NUMBER OF BRANCHES per question by counting role=="branch"
#    occurrences inside reasoning_tree (a JSON string).
#  • Builds three stacked bar-chart panels (YES / MAYBE / NO correct answers)
#    – x-axis: number of branches
#    – y-axis: number of questions
#    – side-by-side bars: Correct (green) vs Wrong (red)
#  • Single shared legend placed above the panels
#  • Saves PNG named: 02_03_tot_loops.png  (as requested)
#
# Run:  Rscript 03_loops_tot.R
#
# Requires: readr, dplyr, ggplot2, tidyr, patchwork, jsonlite
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(tidyr)
  library(patchwork)
  library(jsonlite)
})

# ── files & output -----------------------------------------------------------
csv_file <- "tot_graphrag_d2.csv"
out_png  <- "02_03_tot_loops.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

FIG_WIDTH_MM <- 180
FIG_H_MM     <- 180
DPI          <- 300

# ── helper: count branches safely -------------------------------------------
count_branches <- function(tree_str) {
  if (is.na(tree_str) || !nzchar(tree_str)) return(NA_integer_)
  # parse JSON array of objects; count role == "branch"
  x <- tryCatch(fromJSON(tree_str), error = function(e) NULL)
  if (is.null(x)) return(NA_integer_)
  if (!("role" %in% names(x))) return(0L)
  sum(tolower(as.character(x$role)) == "branch", na.rm = TRUE)
}

# ── load & tidy --------------------------------------------------------------
raw <- read_csv(csv_file, show_col_types = FALSE)

if (!all(c("prediction","gold_label","reasoning_tree") %in% names(raw))) {
  stop("CSV must contain columns: prediction, gold_label, reasoning_tree")
}

df <- raw %>%
  transmute(
    branches   = vapply(reasoning_tree, count_branches, integer(1)),
    prediction = tolower(trimws(as.character(prediction))),
    gold_label = tolower(trimws(as.character(gold_label))),
    is_correct = prediction == gold_label
  ) %>%
  filter(!is.na(branches), branches >= 0,
         gold_label %in% c("yes","no","maybe"),
         !is.na(prediction), prediction %in% c("yes","no","maybe"))

if (nrow(df) == 0) stop("No valid rows loaded from CSV.")

branch_levels <- sort(unique(df$branches))

# ── colours ------------------------------------------------------------------
cols <- c("Correct" = "#4daf4a",   # green
          "Wrong"   = "#e41a1c")   # red

# ── helper: build one panel --------------------------------------------------
make_panel <- function(gold) {
  df %>%
    filter(gold_label == gold) %>%
    mutate(status = ifelse(is_correct, "Correct", "Wrong")) %>%
    count(branches, status, .drop = FALSE) %>%
    complete(
      branches = branch_levels,
      status   = c("Correct", "Wrong"),
      fill     = list(n = 0)
    ) %>%
    mutate(
      branches_f = factor(branches, levels = branch_levels),
      status_f   = factor(status, levels = c("Correct", "Wrong"))
    ) %>%
    ggplot(aes(branches_f, n, fill = status_f)) +
      geom_col(
        position = position_dodge(.8),
        width = .7,
        colour = "black",
        linewidth = .25
      ) +
      scale_fill_manual(values = cols) +
      labs(
        x        = NULL,
        y        = "Count",
        fill     = NULL,
        subtitle = paste0("Correct Answer = ", toupper(gold))
      ) +
      theme_bw(base_size = 10) +
      theme(
        plot.subtitle    = element_text(hjust = .5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "none"
      )
}

p_yes   <- make_panel("yes")
p_maybe <- make_panel("maybe")
p_no    <- make_panel("no") + labs(x = "Number of branches")

# ── assemble: legend row + panels -------------------------------------------
combined <- (
  guide_area() /             # row 1: shared legend
  (p_yes / p_maybe / p_no)   # rows 2-4: panels
) +
  plot_layout(guides = "collect", heights = c(8, 172)) &
  theme(
    legend.position = "top",
    plot.margin     = margin(4, 4, 4, 4, "mm")
  )

# ── save ---------------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = combined,
  width    = FIG_WIDTH_MM,
  height   = FIG_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)