# 06_wasserstein_bins_heatmap.R
#
# Pairwise 1-Wasserstein distances between STS-B bins (from NEW CSV)
# Prints the matrix to the terminal + saves a heatmap PNG.
#
# Inputs (same folder):
#   - stsb_miniLM_cosines.csv  (columns: sentence1, sentence2, gold_score, bin, cosine)
#
# Output:
#   - stsb_w1_heatmap.png
#
# install.packages(c("readr","dplyr","ggplot2","tidyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(tidyr); library(knitr)
})

# --- files ---------------------------------------------------------------
in_csv  <- "stsb_miniLM_cosines.csv"
out_png <- "stsb_w1_heatmap.png"
if (!file.exists(in_csv)) stop("Missing file: ", in_csv)

# --- load ---------------------------------------------------------------
df <- read_csv(in_csv, show_col_types = FALSE)

# Ensure numeric fields exist
if (!"cosine" %in% names(df)) stop("CSV must contain a 'cosine' column.")
if (!"gold_score" %in% names(df)) stop("CSV must contain a 'gold_score' column.")

df <- df %>%
  mutate(
    cosine     = as.numeric(cosine),
    gold_score = as.numeric(gold_score)
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score))

# --- recompute bins from gold_score (ignore any existing 'bin') ----------
# Robust handling for floating point 5.0 → put exact 5.0s into bin "5"
bin_from_gold <- function(g) {
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

df <- df %>%
  mutate(bin = vapply(gold_score, bin_from_gold, character(1)))

# Canonical bin order; keep only bins that are present
bin_levels <- c("0–1","1–2","2–3","3–4","4–5","5")
df <- df %>%
  mutate(bin = factor(bin, levels = bin_levels, ordered = TRUE)) %>%
  filter(!is.na(bin))
present_bins <- levels(droplevels(df$bin))
present_bins <- present_bins[!is.na(present_bins)]
B <- length(present_bins)

# Quick sanity check: counts per bin
cat("\nCounts per bin (recomputed from gold_score):\n")
print(df %>% count(bin) %>% arrange(bin))

# --- 1-Wasserstein distance (quantile integral approximation) -----------
w1_quantile <- function(x, y, m = 1000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# Build symmetric W1 matrix over present bins
W <- matrix(NA_real_, nrow = B, ncol = B,
            dimnames = list(present_bins, present_bins))

for (i in seq_len(B)) {
  xi <- df %>% filter(bin == present_bins[i]) %>% pull(cosine)
  for (j in seq_len(B)) {
    if (i == j) {
      W[i, j] <- 0
    } else {
      yj <- df %>% filter(bin == present_bins[j]) %>% pull(cosine)
      W[i, j] <- w1_quantile(xi, yj, m = 1000)
    }
  }
}

# --- print matrix (rounded) ---------------------------------------------
cat("\n1-Wasserstein distance matrix between STS-B bins (cosine in [0,1])\n")
cat("Smaller = more similar distributions. Diagonal = 0.\n\n")

W_tbl <- as.data.frame(W) %>%
  mutate(Bin = rownames(W)) %>%
  relocate(Bin)

W_tbl_round <- W_tbl
W_tbl_round[ , -1] <- lapply(W_tbl_round[ , -1, drop = FALSE], function(col) round(col, 4))
print(knitr::kable(W_tbl_round, align = "lcccccc"))

# --- heatmap -------------------------------------------------------------
W_long <- as.data.frame(W) %>%
  mutate(Bin_row = rownames(W)) %>%
  pivot_longer(cols = -Bin_row, names_to = "Bin_col", values_to = "W1")

W_long$Bin_row <- factor(W_long$Bin_row, levels = present_bins, ordered = TRUE)
W_long$Bin_col <- factor(W_long$Bin_col, levels = present_bins, ordered = TRUE)

p <- ggplot(W_long, aes(x = Bin_col, y = Bin_row, fill = W1)) +
  geom_tile(color = "grey85", linewidth = 0.25) +
  geom_text(aes(label = ifelse(is.finite(W1), sprintf("%.3f", W1), "")),
            size = 3) +
  scale_fill_gradientn(
    colours = c("white", "#c6dbef", "#6baed6", "#2171b5"),
    na.value = "grey90",
    limits = c(0, max(W_long$W1, na.rm = TRUE)),
    name = "W1 distance"
  ) +
  coord_fixed() +
  labs(
    x = "Bin",
    y = "Bin"
  ) +
  theme_bw(base_size = 11) +
  theme(
    panel.grid    = element_blank(),
    plot.title    = element_text(hjust = 0.5),
    plot.subtitle = element_text(hjust = 0.5)
  )

ggsave(
  filename = out_png,
  plot     = p,
  width    = 160,  # mm
  height   = 140,  # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("\nSaved heatmap to: ", out_png)