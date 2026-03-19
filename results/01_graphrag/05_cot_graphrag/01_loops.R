#!/usr/bin/env Rscript
# 01_loops.R
# ─────────────────────────────────────────────────────────────
# Histogram of loop-counts per PubMed-QA question, coloured by
# the model’s final prediction (yes / no / maybe).
#
#  • Default CSV : cot_graphrag_d1.csv
#  • Output PNG  : 01_loop_hist.png
#
# Override CSV via:
#     Rscript 01_loops.R  some_file.csv
# ─────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2);  library(scales)
})

# ── geometry -------------------------------------------------
PLOT_WIDTH_MM  <- 180
PLOT_HEIGHT_MM <- 120
MARGIN_MM      <- 8

# ── files ----------------------------------------------------
args     <- commandArgs(trailingOnly = TRUE)
csv_file <- if (length(args) >= 1) args[1] else "cot_graphrag_d1.csv"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)
out_png  <- "01_loop_hist.png"

# ── load & tidy ---------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    loops      = as.numeric(loops),
    prediction = tolower(trimws(prediction))
  ) %>%
  filter(prediction %in% c("yes", "no", "maybe") & !is.na(loops))

if (nrow(df) == 0) stop("No usable rows after filtering.")

# ── colour palette ------------------------------------------
ans_cols  <- c("yes"   = "#1f77b4",   # blue
               "maybe" = "#ffdf00",   # yellow
               "no"    = "#d62728")   # red

# ── histogram ------------------------------------------------
p <- ggplot(df, aes(x = loops, fill = prediction)) +
  geom_histogram(binwidth = 1, boundary = 0, closed = "left",
                 colour = "black", linewidth = 0.35,
                 alpha = 0.55, position = "identity") +
  scale_fill_manual(values = ans_cols, name = "Prediction") +
  scale_x_continuous(breaks = pretty(df$loops),
                     minor_breaks = NULL,
                     name = "Loops per question") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.05)),
                     name = "Count") +
  ggtitle("Histogram of loops by model decision") +
  theme_bw(base_size = 12) +
  theme(
    plot.title       = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank(),
    legend.position  = "top",
    plot.margin      = margin(MARGIN_MM, MARGIN_MM,
                              MARGIN_MM, MARGIN_MM, "mm")
  )

# ── save -----------------------------------------------------
ggsave(
  filename = out_png,
  plot     = p,
  width    = PLOT_WIDTH_MM,
  height   = PLOT_HEIGHT_MM,
  units    = "mm",
  dpi      = 300,
  bg       = "white"
)

message("✅  Histogram saved to: ", out_png)