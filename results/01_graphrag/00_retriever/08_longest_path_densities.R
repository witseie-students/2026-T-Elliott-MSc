# 08_longest_path_histogram.R
# ════════════════════════════════════════════════════════════════════════════
# Histogram of longest-shortest-path lengths (max_hops) per paragraph.
#
# • Input : paragraph_longest_paths.csv   (same directory)
# • Output: 08_longest_path_histogram.png (same directory)
# • Bin width = 1 (integer hops), grey bars, black outline
# ════════════════════════════════════════════════════════════════════════════

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2)
})

# ── I/O ---------------------------------------------------------------------
csv_file <- "paragraph_longest_paths.csv"
out_png  <- "08_longest_path_histogram.png"
if (!file.exists(csv_file))
  stop("Missing file: ", csv_file, call. = FALSE)

# ── FIGURE SIZE -------------------------------------------------------------
FIG_W_MM <- 180
FIG_H_MM <-  80
DPI      <- 300

# ── load data ---------------------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
        mutate(max_hops = as.integer(max_hops)) %>%
        filter(!is.na(max_hops))
if (nrow(df) == 0)
  stop("No rows with valid `max_hops` found.", call. = FALSE)

# ── plot --------------------------------------------------------------------
p <- ggplot(df, aes(x = max_hops)) +
  geom_histogram(
    binwidth = 1,
    boundary = -0.5,            # centres bins on integer values
    closed   = "right",
    fill     = "grey80",
    colour   = "black",
    linewidth = 0.3
  ) +
  scale_x_continuous(
    breaks = pretty(df$max_hops, n = 15),
    minor_breaks = NULL,
    expand = c(0.01, 0.01)
  ) +
  labs(
    title = "Distribution of paragraph-level maximum hops",
    x     = "Maximum hops",
    y     = "Count"
  ) +
  theme_bw(base_size = 11) +
  theme(
    plot.title       = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank()
  )

# ── save --------------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = p,
  width    = FIG_W_MM,
  height   = FIG_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)