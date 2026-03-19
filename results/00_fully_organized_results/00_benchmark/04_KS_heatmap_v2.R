#!/usr/bin/env Rscript
# 07_ks_bins_heatmap_lower_revY.R
#
# Pair-wise two-sample KS D-statistics between STS-B bins.
# Shows ONLY the LOWER triangle (incl. diagonal) with the y-axis
# reversed so 0–1 is at the top and 5 at the bottom.
#
# Usage:
#   Rscript 07_ks_bins_heatmap_lower_revY.R          # default CSV
#   Rscript 07_ks_bins_heatmap_lower_revY.R my.csv   # custom CSV
#
# Requires:
#   install.packages(c("readr","dplyr","ggplot2","tidyr","knitr"))

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2)
  library(tidyr);  library(knitr)
})

# ── inputs ────────────────────────────────────────────────────────────────
args    <- commandArgs(trailingOnly = TRUE)
in_csv  <- if (length(args) >= 1) args[1] else "stsb_miniLM_cosines.csv"
out_png <- "04_02_stsb_ks_heatmap_lower_revY_v2.png"
if (!file.exists(in_csv)) stop("Missing file: ", in_csv)

# ── load & tidy ───────────────────────────────────────────────────────────
df_raw <- read_csv(in_csv, show_col_types = FALSE)
need_cols <- c("gold_score","cosine")
if (!all(need_cols %in% names(df_raw)))
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))

df <- df_raw %>%
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = pmin(pmax(as.numeric(cosine), 0), 1)
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score))

# Recompute bins (robust 5.0 handling)
bin_from_gold <- function(g) {
  if (g >= 4.999) return("5")
  if (g >= 4)     return("4–5")
  if (g >= 3)     return("3–4")
  if (g >= 2)     return("2–3")
  if (g >= 1)     return("1–2")
  return("0–1")
}
df <- df %>% mutate(bin = vapply(gold_score, bin_from_gold, character(1)))

bin_levels <- c("0–1","1–2","2–3","3–4","4–5","5")
df <- df %>%
  mutate(bin = factor(bin, levels = bin_levels, ordered = TRUE)) %>%
  filter(!is.na(bin))

present_bins <- levels(droplevels(df$bin))
B <- length(present_bins)

# ── NEW: display labels (plot/print only; no effect on calculations) ───────
bin_display <- c(
  "0–1" = "0",
  "1–2" = "1",
  "2–3" = "2",
  "3–4" = "3",
  "4–5" = "4",
  "5"   = "5"
)
present_bins_disp <- unname(bin_display[present_bins])

cat("\nCounts per bin:\n")
print(df %>% count(bin) %>% arrange(bin) %>% mutate(bin = unname(bin_display[as.character(bin)])))

# ── KS D-statistic matrix (full, symmetric) ───────────────────────────────
ks_D <- function(x, y) {
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  stats::ks.test(x, y, exact = FALSE)$statistic[[1]]
}

K <- matrix(NA_real_, nrow = B, ncol = B,
            dimnames = list(present_bins, present_bins))

for (i in seq_len(B)) {
  xi <- df %>% filter(bin == present_bins[i]) %>% pull(cosine)
  for (j in seq_len(B)) {
    if (i == j) {
      K[i, j] <- 0
    } else {
      yj <- df %>% filter(bin == present_bins[j]) %>% pull(cosine)
      K[i, j] <- ks_D(xi, yj)
    }
  }
}

# ── print rounded matrix to terminal ──────────────────────────────────────
cat("\nTwo-sample KS D matrix between STS-B bins (diagonal = 0)\n\n")
K_tbl <- as.data.frame(K) %>%
  mutate(Bin = rownames(K)) %>%
  relocate(Bin)

# NEW: relabel rows/cols for printing only
colnames(K_tbl) <- c("Bin", present_bins_disp)
K_tbl$Bin <- unname(bin_display[as.character(K_tbl$Bin)])

K_tbl_round <- K_tbl
K_tbl_round[ , -1] <- lapply(K_tbl_round[ , -1], \(col) round(col, 4))
print(knitr::kable(K_tbl_round, align = "lcccccc"))

# ── reshape & keep LOWER triangle (row index ≥ col index) ─────────────────
K_long <- as.data.frame(K) %>%
  mutate(Bin_row = rownames(K)) %>%
  pivot_longer(cols = -Bin_row, names_to = "Bin_col", values_to = "KS") %>%
  mutate(
    idx_row = match(Bin_row, present_bins),
    idx_col = match(Bin_col, present_bins)
  ) %>%
  filter(idx_row >= idx_col) %>%           # lower-triangular cells only
  mutate(
    Bin_row = factor(Bin_row, levels = present_bins, ordered = TRUE),
    Bin_col = factor(Bin_col, levels = present_bins, ordered = TRUE)
  )

# ── heat-map (y-axis flipped) ─────────────────────────────────────────────
p <- ggplot(K_long, aes(x = Bin_col, y = Bin_row, fill = KS)) +
  geom_tile(color = "grey85", linewidth = 0.25) +
  geom_text(aes(label = ifelse(is.finite(KS), sprintf("%.3f", KS), "")),
            size = 3) +
  scale_fill_gradientn(
    colours = c("white", "#c6dbef", "#6baed6", "#2171b5"),
    limits  = c(0, max(K_long$KS, na.rm = TRUE)),
    name    = "KS D"
  ) +
  # NEW: keep ordering identical but show labels as 0..5
  scale_x_discrete(labels = function(x) unname(bin_display[x])) +
  scale_y_discrete(limits = rev(present_bins), labels = function(x) unname(bin_display[x])) +
  coord_fixed() +
  labs(
    x = "Bin", y = "Bin"
  ) +
  theme_bw(base_size = 11) +
  theme(
    panel.grid    = element_blank(),
    plot.title    = element_text(hjust = 0.5, size = 13, family = "Times"),
    plot.subtitle = element_text(hjust = 0.5, size = 10, family = "Times")
  )

ggsave(
  filename = out_png,
  plot     = p,
  width    = 160,   # mm  (consistent with earlier heat-maps)
  height   = 140,   # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("\nSaved lower-triangle KS heat-map to: ", out_png)