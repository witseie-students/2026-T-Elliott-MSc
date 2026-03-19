#!/usr/bin/env Rscript
# 09_welch_p_bins_heatmap.R  (direction-fixed)
#
# Heat-map of one-tailed Welch p-values between STS-B bins.
#   • Upper triangle:  p(mean_row < mean_col)    (alternative = "less")
#   • Lower triangle:  p(mean_row > mean_col)    (alternative = "greater")
#
# Output: stsb_p_heatmap.png   (160 × 140 mm @ 900 dpi)
#
# Requires:
#   install.packages(c("readr","dplyr","ggplot2","tidyr","knitr"))

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2)
  library(tidyr);  library(knitr)
})

# ── I/O ──────────────────────────────────────────────────────────────────
args    <- commandArgs(trailingOnly = TRUE)
in_csv  <- if (length(args) >= 1) args[1] else "stsb_miniLM_cosines.csv"
out_png <- "stsb_p_heatmap.png"
if (!file.exists(in_csv)) stop("Missing file: ", in_csv)

# ── load & tidy ──────────────────────────────────────────────────────────
df_raw <- read_csv(in_csv, show_col_types = FALSE)
need_cols <- c("gold_score", "cosine")
if (!all(need_cols %in% names(df_raw)))
  stop("CSV must contain columns: ", paste(need_cols, collapse = ", "))

df <- df_raw %>%
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = pmin(pmax(as.numeric(cosine), 0), 1)
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score))

# Re-bin (robust 5.0 handling)
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

cat("\nCounts per bin:\n")
print(df %>% count(bin) %>% arrange(bin))

# ── helper: one-tailed Welch p-value ─────────────────────────────────────
p_val <- function(x, y, tail = c("greater", "less")) {
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  t.test(x, y, var.equal = FALSE, alternative = match.arg(tail))$p.value
}

# ── build matrix with correct tail directions ────────────────────────────
P <- matrix(NA_real_, nrow = B, ncol = B,
            dimnames = list(present_bins, present_bins))

for (i in seq_len(B)) {
  xi <- df %>% filter(bin == present_bins[i]) %>% pull(cosine)
  for (j in seq_len(B)) {
    yj <- df %>% filter(bin == present_bins[j]) %>% pull(cosine)
    if (i == j) {
      P[i, j] <- NA_real_                 # diagonal left blank
    } else if (i < j) {
      P[i, j] <- p_val(xi, yj, "less")    # upper: mean_i < mean_j
    } else {                              # i > j
      P[i, j] <- p_val(xi, yj, "greater") # lower: mean_i > mean_j
    }
  }
}

# ── print rounded matrix -------------------------------------------------
cat("\nOne-tailed Welch p-values between STS-B bins\n")
cat("Upper: mean_row < mean_col   |   Lower: mean_row > mean_col\n\n")

P_tbl <- as.data.frame(P) %>%
  mutate(Bin = rownames(P)) %>%
  relocate(Bin)
P_tbl_round <- P_tbl
P_tbl_round[ , -1] <- lapply(P_tbl_round[ , -1], function(col)
  ifelse(is.na(col), "", formatC(col, digits = 3, format = "e")))
print(knitr::kable(P_tbl_round, align = "lcccccc"))

# ── reshape for ggplot ---------------------------------------------------
P_long <- as.data.frame(P) %>%
  mutate(Bin_row = rownames(P)) %>%
  pivot_longer(cols = -Bin_row, names_to = "Bin_col", values_to = "p") %>%
  mutate(
    Bin_row = factor(Bin_row, levels = present_bins, ordered = TRUE),
    Bin_col = factor(Bin_col, levels = present_bins, ordered = TRUE)
  )

# log-scale colour (−log10 p), keep labels as raw p
P_long$logp <- -log10(P_long$p)
log_max <- max(P_long$logp, na.rm = TRUE)

p <- ggplot(P_long, aes(x = Bin_col, y = Bin_row, fill = logp)) +
  geom_tile(color = "grey85", linewidth = 0.25) +
  geom_text(aes(label = ifelse(is.na(p), "", sprintf("%.3g", p))),
            size = 2.7) +
  scale_fill_gradientn(
    colours = c("white", "#c6dbef", "#6baed6", "#2171b5"),
    limits  = c(0, log_max),
    name    = expression(-log[10](p))
  ) +
  coord_fixed() +
  labs(
    title    = "One-tailed Welch p-values between STS-B Bins",
    subtitle = "Upper:  H\u2081: mean\u2099 < mean\u2098   |   Lower:  H\u2081: mean\u2099 > mean\u2098",
    x = "Bin", y = "Bin"
  ) +
  theme_bw(base_size = 11) +
  theme(
    panel.grid    = element_blank(),
    plot.title    = element_text(hjust = 0.5, size = 13, family = "Times"),
    plot.subtitle = element_text(hjust = 0.5, size = 9.5, family = "Times")
  )

ggsave(
  filename = out_png,
  plot     = p,
  width    = 160, height = 140, units = "mm",
  dpi      = 900, bg = "white"
)

message("\nSaved p-value heat-map to: ", out_png)