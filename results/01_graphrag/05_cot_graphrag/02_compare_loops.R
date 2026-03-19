#!/usr/bin/env Rscript

# 02_compare_loops.R
# ---------------------------------------------------------------------------
#  • Reads cot_graphrag_d1.csv
#  • Builds three stacked bar-chart panels (YES / MAYBE / NO correct answers)
#    – x-axis: loops
#    – y-axis: number of questions
#    – side-by-side bars: Correct (green) vs Wrong (red)
#  • Single shared legend placed above the panels
#  • Saves 02_cot_graphrag_d1_loops_correct_vs_wrong_by_gold.png
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(tidyr)
  library(patchwork)
})

# ── files & output -----------------------------------------------------------
csv_file <- "cot_graphrag_d1.csv"
out_png  <- "02_cot_graphrag_d1_loops_correct_vs_wrong_by_gold.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

FIG_WIDTH_MM <- 180
FIG_H_MM     <- 180
DPI          <- 300

# ── load & tidy --------------------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  transmute(
    loops      = as.integer(loops),
    prediction = tolower(trimws(as.character(prediction))),
    gold_label = tolower(trimws(as.character(gold_label))),
    is_correct = prediction == gold_label
  ) %>%
  filter(!is.na(loops), loops >= 0, gold_label %in% c("yes","no","maybe"))

loop_levels <- sort(unique(df$loops))

# ── colours ------------------------------------------------------------------
cols <- c("Correct" = "#4daf4a",   # green
          "Wrong"   = "#e41a1c")   # red

# ── helper: build one panel --------------------------------------------------
make_panel <- function(gold) {
  df %>%
    filter(gold_label == gold) %>%
    mutate(status = ifelse(is_correct, "Correct", "Wrong")) %>%
    count(loops, status, .drop = FALSE) %>%
    complete(
      loops  = loop_levels,
      status = c("Correct", "Wrong"),
      fill   = list(n = 0)
    ) %>%
    mutate(
      loops_f  = factor(loops,  levels = loop_levels),
      status_f = factor(status, levels = c("Correct", "Wrong"))
    ) %>%
    ggplot(aes(loops_f, n, fill = status_f)) +
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
p_no    <- make_panel("no") + labs(x = "Total loops")

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