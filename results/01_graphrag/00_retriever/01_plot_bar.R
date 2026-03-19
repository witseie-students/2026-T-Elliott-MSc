# 01_plot_bar.R
# ─────────────────────────────────────────────────────────────────────────────
# Read retrieval.csv, draw a bar chart (rank 1..N on x-axis) and place a
# nicely-formatted table with questions + cosine similarities *below* the plot.
#
# Run in the folder that contains retrieval.csv:
#     Rscript 01_plot_bar.R
#
# Required libraries:
#   install.packages(c("readr","dplyr","ggplot2","scales",
#                      "gridExtra","patchwork","stringr"))
# ─────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(scales)
  library(gridExtra)
  library(patchwork)
  library(stringr)
})

# ── geometry knobs ----------------------------------------------------------
INNER_WIDTH_MM   <- 260   # bar-plot width
PLOT_HEIGHT_MM   <- 120   # bar-plot height
TABLE_HEIGHT_MM  <- 110   # table height
EXTRA_MARGIN_MM  <- 10    # uniform outer margin

TOTAL_WIDTH_MM   <- INNER_WIDTH_MM + 2*EXTRA_MARGIN_MM
TOTAL_HEIGHT_MM  <- PLOT_HEIGHT_MM + TABLE_HEIGHT_MM + 2*EXTRA_MARGIN_MM

# ── files -------------------------------------------------------------------
csv_file <- "retrieval.csv"
out_png  <- "retrieval_with_table.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

# ── load --------------------------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    rank              = as.integer(rank),
    rank_f            = factor(rank, levels = rank)   # for discrete x-axis
  )

# ── bar plot ----------------------------------------------------------------
BAR_WIDTH   <- 0.55
FILL        <- "#80b1d3"
LAB_SIZE    <- 3.0

p_bar <- ggplot(df, aes(x = rank_f, y = cosine_similarity)) +
  geom_col(width = BAR_WIDTH, fill = FILL, colour = "black", linewidth = 0.35) +
  geom_text(aes(label = sprintf("%.3f", cosine_similarity)),
            vjust = -0.4, size = LAB_SIZE) +
  scale_y_continuous(limits = c(0, 1.1),
                     breaks = seq(0,1,0.1),
                     labels = number_format(accuracy = 0.1),
                     expand = c(0.01, 0)) +
  labs(
    title = "Cosine similarity of retrieved questions",
    x     = "Rank (1 = closest)",
    y     = "Cosine similarity"
  ) +
  theme_bw(base_size = 12) +
  theme(
    plot.title       = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank(),
    plot.margin      = margin(EXTRA_MARGIN_MM, EXTRA_MARGIN_MM,
                              EXTRA_MARGIN_MM/2, EXTRA_MARGIN_MM, "mm")
  )

# ── table (wrap long questions) --------------------------------------------
table_df <- df %>%
  transmute(
    `#`        = rank,
    Question   = str_wrap(question, width = 80),
    CosSim     = sprintf("%.3f", cosine_similarity)
  )

table_grob <- tableGrob(
  table_df,
  rows  = NULL,
  theme = ttheme_minimal(
    base_size = 8,
    core = list(fg_params = list(hjust = 0, x = 0.05))
  )
)

# ── combine with patchwork ---------------------------------------------------
combined <- p_bar / table_grob +
  plot_layout(heights = c(PLOT_HEIGHT_MM, TABLE_HEIGHT_MM)) &
  theme(plot.margin = margin(0,0,0,0))

# ── save --------------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = combined,
  width    = TOTAL_WIDTH_MM,
  height   = TOTAL_HEIGHT_MM,
  units    = "mm",
  dpi      = 300,
  bg       = "white"
)

message("✅  Plot + table saved to: ", out_png)