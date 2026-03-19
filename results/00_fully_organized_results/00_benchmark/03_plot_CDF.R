#!/usr/bin/env Rscript
# 04_stsb_ecdf_bins.R
#
# Overlay ECDFs for each STS-B rating bin (with a true “5” bin),
# using the same colour palette and theme conventions as
# 03_stsb_density_box_pairs_full.R.
#
# Usage:
#   Rscript 04_stsb_ecdf_bins.R           # default CSV name
#   Rscript 04_stsb_ecdf_bins.R my.csv    # custom CSV
#
# Required:
#   install.packages(c("readr","dplyr","ggplot2","scales","viridisLite"))

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(scales)
})

# ── inputs ────────────────────────────────────────────────────────────────
args      <- commandArgs(trailingOnly = TRUE)
csv_file  <- if (length(args) >= 1) args[1] else "stsb_miniLM_cosines.csv"
out_png   <- "03_stsb_bins_ecdf_full.png"

if (!file.exists(csv_file)) stop("Missing file: ", csv_file)

# ── load & tidy ──────────────────────────────────────────────────────────
df_raw <- read_csv(csv_file, show_col_types = FALSE)
need_cols <- c("gold_score","bin","cosine")
if (!all(need_cols %in% names(df_raw))) {
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))
}

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

# ── compute per-bin medians for colour mapping ───────────────────────────
summary_df <- df %>%
  group_by(bin) %>%
  summarise(median = median(cosine), .groups = "drop")

anchor_cols <- c("#fbb4ae", "#fff2ae", "#b3e2cd")  # pastel R → A → M
grad_fun    <- colorRampPalette(anchor_cols)
cols_cont   <- grad_fun(1000)
col_for_val <- function(x) cols_cont[pmax(1, pmin(1000, round(x*999)+1))]
bin_cols    <- setNames(col_for_val(summary_df$median), summary_df$bin)

# ── plot ECDFs ───────────────────────────────────────────────────────────
p <- ggplot(df, aes(x = cosine, colour = bin)) +
  stat_ecdf(geom = "step", linewidth = 0.8) +
  scale_x_continuous(
    limits = c(0, 1),
    breaks = seq(0, 1, 0.1),
    expand = c(0, 0)
  ) +
  scale_colour_manual(values = bin_cols, name = "STS-B\nbin") +
  labs(
    x        = "Cosine similarity",
    y        = "Empirical CDF"
  ) +
  theme_bw(base_size = 11) +
  theme(
    plot.title      = element_text(hjust = 0.5, size = 13, family = "Times"),
    plot.subtitle   = element_text(hjust = 0.5, size = 10, family = "Times"),
    legend.title    = element_text(size = 10),
    legend.text     = element_text(size = 9),
    panel.grid.minor= element_blank()
  )

print(p)

# ── save (HD, same dpi & mm units as your density/box script) ────────────
ggsave(
  filename = out_png,
  plot     = p,
  width    = 200,   # mm
  height   = 130,   # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved ECDF figure to: ", out_png)