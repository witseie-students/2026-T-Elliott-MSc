# 04_compare_answers.R
# ────────────────────────────────────────────────────────────────────────────
# Visualise cosine-similarity distributions split by the PubMedQA answer
# label (yes / maybe / no).
#
# • Reads  question_cosines.csv   (columns: pubid, question, answer, rank …)
# • Creates:
#       – 3 stacked histograms   (yes → maybe → no)
#       – 1 box-and-whisker panel comparing the three classes
# • Saves  answer_cosines_hist_box.png  next to the CSV
#
# Run:  Rscript 04_compare_answers.R
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
out_png  <- "answer_cosines_hist_box.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file, call. = FALSE)

# ── FIGURE GEOMETRY (edit freely) -----------------------------------------
HIST_HEIGHT_MM  <- 60     # height for each histogram panel
BOX_HEIGHT_MM   <- 70     # height for bottom box-plot panel
FIG_WIDTH_MM    <- 180    # width of entire figure
DPI             <- 300
BIN_W           <- 0.005  # bin width (2.5 %)

# ── Load + basic cleaning --------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    answer            = tolower(trimws(answer)),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1)
  ) %>%
  filter(answer %in% c("yes","no","maybe"),
         !is.na(cosine_similarity))

if (nrow(df) == 0) stop("No rows with yes / maybe / no answers found.", call. = FALSE)

# ── palette ----------------------------------------------------------------
ans_levels <- c("yes","maybe","no")
df$answer  <- factor(df$answer, levels = ans_levels, ordered = TRUE)
fill_cols  <- setNames(c("#8dd3c7", "#ffffb3", "#fb8072"), ans_levels)  # teal, yellow, coral

# ── helper: one histogram panel -------------------------------------------
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

# ── bottom: box-and-whisker across classes ---------------------------------
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
    subtitle = "Box-and-whisker by answer label"
  ) +
  theme_bw(base_size = 11) +
  theme(
    legend.position  = "none",
    plot.subtitle    = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank()
  )

# ── assemble & save --------------------------------------------------------
combined <- p_hist_stack / p_box +
  plot_layout(heights = c(
    rep(HIST_HEIGHT_MM, length(ans_levels)),  # three histograms
    BOX_HEIGHT_MM
  )) &
  theme(plot.margin = margin(4,4,4,4,"mm"))

ggsave(
  filename = out_png,
  plot     = combined,
  width    = FIG_WIDTH_MM,
  height   = HIST_HEIGHT_MM*length(ans_levels) + BOX_HEIGHT_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)