# 06_density_threshold.R  (two thresholds, arrows toward lines)
# ────────────────────────────────────────────────────────────────────────────
# • Rank-1 neighbours only
# • Grey density + grey horizontal box-plot
# • Two dashed thresholds, each with an arrow-label on the density panel
#   – Q₁ of STS-B Bin 3-4  at 0.661  (label on the RIGHT, arrow head at line)
#   – Q₃ of STS-B Bin 1-2  at 0.543  (label on the LEFT,  arrow head at line)
# • Output: 00_top1_density_threshold.png
# ────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(scales)
})

# ── I/O --------------------------------------------------------------------
csv_file <- "question_cosines.csv"
out_png  <- "01_top1_density_threshold_v2.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file, call. = FALSE)

# ── FIGURE SIZING ----------------------------------------------------------
FIG_W_MM  <- 180
DENS_H_MM <-  80
BOX_H_MM  <-  30
DPI       <- 300

# thresholds & labels -------------------------------------------------------
THRESH1 <- 0.661                      # Q₁
THRESH2 <- 0.543                      # Q₃
LABEL1  <- "Q\u2081 of STS-B Bin 3" # unicode sub-1
LABEL2  <- "Q\u2083 of STS-B Bin 1" # unicode sub-3

# ── load & keep Rank-1 -----------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1)
  ) %>%
  filter(rank == 1, !is.na(cosine_similarity))
if (nrow(df) == 0) stop("No Rank-1 rows found.", call. = FALSE)

FILL_GREY <- "grey80"

# density panel -------------------------------------------------------------
adjust_k  <- 0.4
dens_obj  <- density(df$cosine_similarity, adjust = adjust_k, from = 0, to = 1)
dens_ymax <- max(max(dens_obj$y) * 1.05, 7)   # ensure ≥ 7 units head-room

# label coordinates
lab1_x <- THRESH1 + 0.08; lab1_y <- dens_ymax * 0.90   # right of 0.661
lab2_x <- THRESH2 - 0.08; lab2_y <- dens_ymax * 0.75   # left  of 0.543

p_dens <- ggplot(df, aes(x = cosine_similarity)) +
  geom_density(fill = FILL_GREY, colour = "black", alpha = 0.9,
               adjust = adjust_k, linewidth = 0.3) +
  geom_vline(xintercept = c(THRESH1, THRESH2),
             linetype = "dashed", linewidth = 0.5) +

  # ── arrow + label for THRESH1  (arrow head AT dashed line) ─────────────
  annotate("segment",
           x = lab1_x - 0.02, xend = THRESH1 + 0.01,
           y = lab1_y,        yend = lab1_y,
           linewidth = 0.4,
           arrow = arrow(length = unit(3, "pt"), type = "closed")) +
  annotate("text",
           x = lab1_x, y = lab1_y,
           label = LABEL1, hjust = 0, vjust = 0.5, size = 3) +

  # ── arrow + label for THRESH2  (arrow head AT dashed line) ─────────────
  annotate("segment",
           x = lab2_x + 0.02, xend = THRESH2 - 0.01,
           y = lab2_y,        yend = lab2_y,
           linewidth = 0.4,
           arrow = arrow(length = unit(3, "pt"), type = "closed")) +
  annotate("text",
           x = lab2_x, y = lab2_y,
           label = LABEL2, hjust = 1, vjust = 0.5, size = 3) +

  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1), expand = c(0,0)) +
  scale_y_continuous(limits = c(0, dens_ymax), expand = c(0,0)) +
  labs(title = "Rank-1 neighbour cosine-similarity distribution",
       x = NULL, y = "Density") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank())

# box-plot panel ------------------------------------------------------------
p_box <- ggplot(df, aes(x = cosine_similarity, y = factor(1))) +
  geom_boxplot(fill = FILL_GREY, colour = "black",
               linewidth = 0.3, width = 0.6,
               outlier.shape = 16, outlier.size = 1.2) +
  geom_vline(xintercept = c(THRESH1, THRESH2),
             linetype = "dashed", linewidth = 0.5) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1), expand = c(0,0)) +
  scale_y_discrete(labels = NULL) +
  labs(x = "Cosine similarity", y = NULL,
       subtitle = "Horizontal box-and-whisker (Rank-1 only)") +
  theme_bw(base_size = 11) +
  theme(axis.ticks.y     = element_blank(),
        plot.subtitle    = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank())

# combine & save ------------------------------------------------------------
ggsave(
  filename = out_png,
  plot     = (p_dens / p_box) +
             plot_layout(heights = c(DENS_H_MM, BOX_H_MM)) &
             theme(plot.margin = margin(4,4,4,4, "mm")),
  width  = FIG_W_MM,
  height = DENS_H_MM + BOX_H_MM,
  units  = "mm",
  dpi    = DPI,
  bg     = "white"
)

message("✅  Figure saved to: ", out_png)