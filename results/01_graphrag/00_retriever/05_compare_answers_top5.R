# 05_compare_answers_top5.R
# ────────────────────────────────────────────────────────────────────────────
# Visualise cosine-similarity distributions for ONLY the Top-5 neighbours
# (rank 1–5) split by PubMedQA answer label (yes / maybe / no).
#
# Generates:
#   • 3 stacked histograms   (yes → maybe → no)
#   • 1 box-and-whisker panel (bottom)
#
# Output PNG:  answer_cosines_top5_hist_box.png
#
# Run:  Rscript 05_compare_answers_top5.R
#
# Required packages:
#   install.packages(c("readr","dplyr","ggplot2","patchwork","scales"))
# ────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})

# ── I/O --------------------------------------------------------------------
csv_file <- "question_cosines.csv"
out_png  <- "answer_cosines_top5_hist_box.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file, call. = FALSE)

# ── FIGURE GEOMETRY --------------------------------------------------------
FIG_WIDTH_MM   <- 180   # overall width
HIST_H_MM      <- 55    # height per histogram
BOX_H_MM       <- 70    # height for bottom box-plot
DPI            <- 300
BIN_W          <- 0.005  # histogram bin width (3 %)

# ── load + filter Top-5 ----------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    answer            = tolower(trimws(answer)),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1)
  ) %>%
  filter(rank <= 1,                    # **Top-5 only**
         answer %in% c("yes","maybe","no"),
         !is.na(cosine_similarity))

if (nrow(df) == 0) stop("No rows with rank ≤ 5 found.", call. = FALSE)

# ── palette ---------------------------------------------------------------
ans_levels <- c("yes","maybe","no")
df$answer  <- factor(df$answer, levels = ans_levels, ordered = TRUE)
fill_cols  <- setNames(c("#8dd3c7", "#ffffb3", "#fb8072"), ans_levels)

# ── helper: histogram for one answer class --------------------------------
make_hist <- function(ans) {
  ggplot(filter(df, answer == ans), aes(x = cosine_similarity)) +
    geom_histogram(
      binwidth = BIN_W, closed = "left",
      fill = fill_cols[[ans]], colour = "black", linewidth = 0.25
    ) +
    scale_x_continuous(
      limits = c(0,1), breaks = seq(0,1,0.2), expand = c(0,0)
    ) +
    labs(
      x = NULL, y = "Count",
      subtitle = paste("Answer:", tools::toTitleCase(ans))
    ) +
    theme_bw(base_size = 10) +
    theme(
      plot.subtitle    = element_text(hjust = 0.5, face = "bold"),
      panel.grid.minor = element_blank()
    )
}

p_hist_stack <- wrap_plots(lapply(ans_levels, make_hist), ncol = 1)

# ── bottom box-and-whisker -------------------------------------------------
p_box <- ggplot(df, aes(x = answer, y = cosine_similarity, fill = answer)) +
  geom_boxplot(
    colour = "black", linewidth = 0.3,
    outlier.shape = 16, outlier.size = 1.2, na.rm = TRUE
  ) +
  scale_fill_manual(values = fill_cols) +
  scale_y_continuous(
    limits = c(0,1), breaks = seq(0,1,0.1), expand = c(0,0)
  ) +
  labs(
    x = NULL, y = "Cosine similarity",
    subtitle = "Box-and-whisker (Top-5 neighbours)"
  ) +
  theme_bw(base_size = 11) +
  theme(
    legend.position  = "none",
    plot.subtitle    = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank()
  )

# ── assemble ----------------------------------------------------------------
combined <- p_hist_stack / p_box +
  plot_layout(heights = c(
    rep(HIST_H_MM, length(ans_levels)),
    BOX_H_MM
  )) &
  theme(plot.margin = margin(4,4,4,4,"mm"))

# ── save --------------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = combined,
  width    = FIG_WIDTH_MM,
  height   = HIST_H_MM*length(ans_levels) + BOX_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)