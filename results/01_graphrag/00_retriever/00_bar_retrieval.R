# 00_bar_retrieval.R
# ─────────────────────────────────────────────────────────────────────────────
# Bar chart (cosine similarity) for retrieval.csv with fully parameterised
# geometry.  Adjust the *constants below* until the PNG looks right.
# ---------------------------------------------------------------------------
# Run:
#   Rscript 00_bar_retrieval.R
#
# Required libraries:
#   install.packages(c("readr","dplyr","ggplot2","scales"))
# ─────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(scales)
})

# ── GEOMETRY CONSTANTS ──────────────────────────────────────────────────────
# Size of the PLOTTING PANEL (bars).
INNER_WIDTH_MM  <- 0.8*260   # mm      ← change these two first
INNER_HEIGHT_MM <- 2*150   # mm

# Extra margins around the panel.
EXTRA_TOP_MM    <- 15    # title & headroom
EXTRA_RIGHT_MM  <- 6*25
EXTRA_BOTTOM_MM <- 55    # room for long, slanted x-labels
EXTRA_LEFT_MM   <- 10

# Derived overall canvas size for ggsave
TOTAL_WIDTH_MM  <- INNER_WIDTH_MM  + EXTRA_LEFT_MM + EXTRA_RIGHT_MM
TOTAL_HEIGHT_MM <- INNER_HEIGHT_MM + EXTRA_TOP_MM  + EXTRA_BOTTOM_MM

# ── FILES ───────────────────────────────────────────────────────────────────
csv_file <- "retrieval.csv"          # must sit in the same folder
out_png  <- "retrieval_bar.png"

if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

# ── LOAD CSV ────────────────────────────────────────────────────────────────
df <- read_csv(csv_file, show_col_types = FALSE)

need_cols <- c("rank","question","sentence","cosine_similarity")
if (!all(need_cols %in% names(df))) {
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))
}

df <- df %>%
  mutate(
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    question = factor(question, levels = question[order(rank)])
  )

# ── STYLE KNOBS (bars & text) ───────────────────────────────────────────────
BAR_WIDTH  <- 0.22
OUTLINE    <- "#2a2a2a"
FILL       <- "#cfe3ff"
LABEL_SIZE <- 3.1        # text above bars

# ── PLOT --------------------------------------------------------------------
p <- ggplot(df, aes(x = question, y = cosine_similarity)) +
  geom_col(width = BAR_WIDTH, fill = FILL, colour = OUTLINE, linewidth = 0.35) +
  geom_text(
    aes(label = sprintf("%.3f", cosine_similarity)),
    vjust = -0.5, size = LABEL_SIZE, family = "sans"
  ) +
  scale_y_continuous(
    limits = c(0, 1.10),
    breaks = seq(0, 1, 0.1),
    labels = number_format(accuracy = 0.1),
    expand = c(0.01, 0)
  ) +
  labs(
    title = "Top retrieved questions — cosine similarity",
    x     = NULL,
    y     = "Cosine similarity (0–1)"
  ) +
  coord_cartesian(clip = "off") +
  theme_bw(base_size = 12) +
  theme(
    axis.text.x = element_text(
      angle   = -45,  # slant down-right
      hjust   = 0,
      vjust   = 1,
      lineheight = 0.9
    ),
    plot.title       = element_text(hjust = 0.5, face = "bold"),
    panel.grid.minor = element_blank(),
    plot.margin      = margin(
      t = EXTRA_TOP_MM,
      r = EXTRA_RIGHT_MM,
      b = EXTRA_BOTTOM_MM,
      l = EXTRA_LEFT_MM,
      unit = "mm"
    )
  )

# ── SAVE --------------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = p,
  width    = TOTAL_WIDTH_MM,
  height   = TOTAL_HEIGHT_MM,
  units    = "mm",
  dpi      = 300,
  bg       = "white"
)

message("✅  Bar chart saved to: ", out_png)