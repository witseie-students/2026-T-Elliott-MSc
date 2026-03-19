# 03_stsb_density_box_pairs_full.R
#
# Density + horizontal box-plot for STS-B bins using the *bin* column
# from your full CSV (so a true "5" bin is included). Colours use a
# pastel Red → Amber → Mint gradient keyed to each bin’s median cosine.
#
# Run:   Rscript 03_stsb_density_box_pairs_full.R
#
# Required:
#   install.packages(c("readr","dplyr","ggplot2","patchwork","scales"))

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})

# ── inputs ────────────────────────────────────────────────────────────────
csv_file <- "stsb_miniLM_cosines.csv"   # from make_stsb_cosines_full.py
out_png  <- "stsb_bins_density_box_fullv2.png"
adjust_k <- 0.4    # KDE bandwidth

if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

# ── load ──────────────────────────────────────────────────────────────────
df_raw <- read_csv(csv_file, show_col_types = FALSE)

need_cols <- c("gold_score","bin","cosine")
if (!all(need_cols %in% names(df_raw))) {
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))
}

# Keep in-range cosines & known bins
std_levels <- c("0–1","1–2","2–3","3–4","4–5","5")
df <- df_raw %>%
  mutate(
    bin    = as.character(bin),
    cosine = pmin(pmax(as.numeric(cosine), 0), 1)
  ) %>%
  filter(!is.na(bin), bin %in% std_levels, !is.na(cosine))

present_levels <- std_levels[std_levels %in% unique(df$bin)]
df$bin <- factor(df$bin, levels = present_levels, ordered = TRUE)

if (nrow(df) == 0) stop("No valid rows after filtering.")

# ── NEW: display labels for plotting only (does NOT affect bin logic) ───────
bin_display <- c(
  "0–1" = "0",
  "1–2" = "1",
  "2–3" = "2",
  "3–4" = "3",
  "4–5" = "4",
  "5"   = "5"
)

# ── per-bin summaries ─────────────────────────────────────────────────────
summary_df <- df %>%
  group_by(bin) %>%
  summarise(
    mean   = mean(cosine),
    median = median(cosine),
    .groups= "drop"
  )

# Optional descriptive text (used in subtitles)
bin_desc <- c(
  "0–1" = "Completely dissimilar.",
  "1–2" = "Not equivalent, but on the same topic.",
  "2–3" = "Not equivalent, but share some details.",
  "3–4" = "Roughly equivalent; important info differs/missing.",
  "4–5" = "Mostly equivalent; unimportant details differ.",
  "5"   = "Completely equivalent in meaning."
)

# ── pastel Red → Amber → Mint gradient keyed to each bin’s median ─────────
anchor_cols <- c("#fbb4ae", "#fff2ae", "#b3e2cd")
grad_fun    <- colorRampPalette(anchor_cols)
cols_cont   <- grad_fun(1000)
col_for_val <- function(x) cols_cont[pmax(1, pmin(1000, round(x*999)+1))]
bin_cols    <- setNames(col_for_val(summary_df$median), summary_df$bin)

# ── helper: density + horizontal box for one bin ─────────────────────────
make_pair <- function(bin_level) {
  dat  <- dplyr::filter(df, bin == bin_level)
  stat <- dplyr::filter(summary_df, bin == bin_level)
  col  <- bin_cols[[as.character(bin_level)]]

  # robust ymax for density panel
  ymax <- tryCatch({
    max(density(dat$cosine, adjust = adjust_k, from = 0, to = 1)$y) * 1.05
  }, error = function(e) 1)

  # NEW: pretty label for plots only
  b_lab <- unname(bin_display[[as.character(bin_level)]])

  p_d <- ggplot(dat, aes(x = cosine)) +
    geom_density(fill = col, colour = "black",
                 adjust = adjust_k, alpha = 0.9, linewidth = 0.3, na.rm = TRUE) +
    geom_vline(aes(xintercept = stat$mean),
               linetype = "dashed", linewidth = 0.4) +
    geom_vline(aes(xintercept = stat$median),
               linetype = "dotted", linewidth = 0.4) +
    scale_x_continuous(limits = c(0,1), expand = c(0,0)) +
    scale_y_continuous(limits = c(0, ymax), expand = c(0,0)) +
    labs(
      x = NULL, y = "Density",
      subtitle = sprintf("Bin %s%s",
                         b_lab,
                         if (!is.null(bin_desc[[as.character(bin_level)]]))
                           paste0(" — ", bin_desc[[as.character(bin_level)]])
                         else "")
    ) +
    theme_bw(base_size = 11) +
    theme(
      plot.subtitle    = element_text(hjust = 0.5, face = "bold"),
      axis.title.x     = element_blank(),
      panel.grid.minor = element_blank()
    )

  # NEW: use a plotting-only factor for y so the displayed labels are 0..5
  dat <- dat %>%
    mutate(bin_plot = factor(bin_display[as.character(bin)],
                             levels = bin_display[levels(df$bin)],
                             ordered = TRUE))

  p_b <- ggplot(dat, aes(x = cosine, y = bin_plot)) +
    geom_boxplot(fill = col, colour = "black",
                 outlier.shape = 16, outlier.size = 1.3,
                 linewidth = 0.4, width = 0.6, na.rm = TRUE) +
    geom_vline(aes(xintercept = stat$mean),
               linetype = "dashed", linewidth = 0.4) +
    geom_vline(aes(xintercept = stat$median),
               linetype = "dotted", linewidth = 0.4) +
    scale_x_continuous(limits = c(0,1), expand = c(0,0)) +
    scale_y_discrete(labels = NULL) +
    labs(x = NULL, y = NULL) +
    theme_bw(base_size = 11) +
    theme(
      axis.ticks.y     = element_blank(),
      panel.grid.minor = element_blank()
    )

  p_d / p_b + plot_layout(heights = c(3, 0.8))
}

pair_plots <- lapply(levels(df$bin), make_pair)
main_stack <- wrap_plots(pair_plots, ncol = 1)

# ── thin colour bar (≈1 % height) ─────────────────────────────────────────
bar_df <- data.frame(x = seq(0,1,length.out = 500), y = 1)
p_bar <- ggplot(bar_df, aes(x = x, y = y, fill = x)) +
  geom_tile() +
  scale_fill_gradientn(colours = grad_fun(500), limits = c(0,1)) +
  scale_x_continuous(breaks = seq(0,1,0.2),
                     labels = number_format(accuracy = 0.1),
                     expand = c(0,0)) +
  scale_y_continuous(expand = c(0,0)) +
  labs(x = "Cosine similarity (0 – 1)", y = NULL) +
  theme_minimal(base_size = 8) +
  theme(
    axis.text.y     = element_blank(),
    axis.title.y    = element_blank(),
    panel.grid      = element_blank(),
    legend.position = "none",
    plot.margin     = margin(0,0,0,0)
  )

# ── assemble final figure ────────────────────────────────────────────────
combined <- p_bar / main_stack +
  plot_annotation(
    title = "Cosine-similarity distributions by STS-B rating bin",
    subtitle = "Density (top) with mean (dashed) & median (dotted); horizontal box-plot (bottom).",
    theme = theme(
      plot.title    = element_text(hjust = 0.5, size = 13, family = "Times"),
      plot.subtitle = element_text(hjust = 0.5, size = 10, family = "Times")
    )
  ) +
  plot_layout(heights = c(0.01, 1))   # colour bar ~1 % of total height

# ── save (HD) ────────────────────────────────────────────────────────────
ggsave(
  filename = out_png,
  plot     = combined,
  width    = 200,   # mm
  height   = 390,   # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved combined figure to: ", out_png)