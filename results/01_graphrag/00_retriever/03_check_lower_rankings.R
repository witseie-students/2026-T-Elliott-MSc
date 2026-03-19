# 03_check_lower_rankings.R
# ─────────────────────────────────────────────────────────────────────────────
#  • Read question_cosines.csv (pubid, question, rank, cosine_similarity)
#  • Identify the 20 LOWEST-similarity rank-1 rows (worst cases)
#  • Keep all rows whose pubid is in that bottom-20 set
#  • Produce the *same* stacked-histogram + box-plot figure as script 02
#  • Output file:  question_cosines_LOW20.png
#
# Run:  Rscript 03_check_lower_rankings.R
#
# Requires:  readr, dplyr, ggplot2, patchwork
# ─────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(patchwork)
})

# ── files & figure geometry --------------------------------------------------
csv_file <- "question_cosines.csv"
out_png  <- "question_cosines_LOW20.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

FIG_WIDTH_MM <- 180    # change if you need wider
HIST_H_MM    <-  40    # per-hist height
BOXES_H_MM   <-  70    # box-plot stack
DPI          <- 300
BIN_W        <- 0.025  # histogram bin width
LOW_N        <- 5     # how many worst rank-1 rows to consider

# ── load CSV ---------------------------------------------------------------
df_raw <- read_csv(csv_file, show_col_types = FALSE) %>%
  transmute(
    pubid = as.character(pubid),
    rank  = as.integer(rank),
    cos   = pmin(pmax(as.numeric(cosine_similarity), 0), 1)
  ) %>%
  filter(!is.na(rank), !is.na(cos))

if (nrow(df_raw) == 0) stop("No rows in CSV!")

# ── find bottom-20 rank-1 rows ---------------------------------------------
bottom_ids <- df_raw %>%
  filter(rank == 1) %>%
  arrange(cos) %>%          # ascending = worst first
  slice_head(n = LOW_N) %>%
  pull(pubid)

df <- df_raw %>%
  filter(pubid %in% bottom_ids) %>%            # keep only low performers
  mutate(
    band = case_when(
      rank == 1  ~ "rank-1",
      rank <= 5  ~ "1–5",
      rank <=10  ~ "6–10",
      rank <=15  ~ "11–15",
      TRUE       ~ "16–20"
    )
  )

if (nrow(df) == 0) stop("After filtering, no rows remain – check CSV!")

# ── colour mapping ----------------------------------------------------------
band_levels <- c("rank-1","1–5","6–10","11–15","16–20")
band_cols   <- c(
  "rank-1" = "#ffd92f",
  "1–5"    = "#66c2a5",
  "6–10"   = "#fc8d62",
  "11–15"  = "#8da0cb",
  "16–20"  = "#e78ac3"
)

# ── helper: histogram for a band -------------------------------------------
make_hist <- function(band_name, subtitle_txt) {
  ggplot(filter(df, band == !!band_name), aes(x = cos)) +
    geom_histogram(
      binwidth = BIN_W, closed = "left",
      fill = band_cols[[band_name]], colour = "black", linewidth = .25
    ) +
    scale_x_continuous(limits = c(0,1), breaks = seq(0,1,.2), expand = c(0,0)) +
    labs(x = NULL, y = "Count", subtitle = subtitle_txt) +
    theme_bw(base_size = 10) +
    theme(
      plot.subtitle    = element_text(hjust = .5, face = "bold"),
      axis.title.y     = element_text(size = 8),
      panel.grid.minor = element_blank()
    )
}

p_rank1 <- make_hist("rank-1",  "Rank-1 (lowest 20 queries)")
p_1_5   <- make_hist("1–5",     "Rank-band 1-5")
p_6_10  <- make_hist("6–10",    "Rank-band 6-10")
p_11_15 <- make_hist("11–15",   "Rank-band 11-15")
p_16_20 <- make_hist("16–20",   "Rank-band 16-20")

hist_stack <- wrap_plots(
  list(p_rank1, p_1_5, p_6_10, p_11_15, p_16_20),
  ncol = 1
)

# ── box-plot stack (ranks 1-5 only) ----------------------------------------
df_top5 <- filter(df, rank <= 5) %>%
  mutate(rank_f = factor(rank, levels = 1:5))

p_boxes <- ggplot(df_top5, aes(x = cos, y = rank_f)) +
  geom_boxplot(
    fill = "#b3e2cd", colour = "black",
    linewidth = .3, outlier.shape = 16, outlier.size = 1.2, na.rm = TRUE
  ) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,.2), expand = c(0,0)) +
  scale_y_discrete(labels = paste("Rank", 1:5)) +
  labs(
    x = "Cosine similarity",
    y = NULL,
    subtitle = "Box-and-whisker (ranks 1-5, bottom-20 queries)"
  ) +
  theme_bw(base_size = 10) +
  theme(
    plot.subtitle    = element_text(hjust = .5, face = "bold"),
    panel.grid.minor = element_blank()
  )

# ── assemble & output -------------------------------------------------------
combined <- hist_stack / p_boxes +
  plot_layout(heights = c(rep(HIST_H_MM, 5), BOXES_H_MM)) &
  theme(plot.margin = margin(4,4,4,4,"mm"))

ggsave(
  filename = out_png,
  plot     = combined,
  width    = FIG_WIDTH_MM,
  height   = 5*HIST_H_MM + BOXES_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)