# 07_w1_triple_vs_qa.R
#
# Compute 1-Wasserstein distances between:
#   • Triple back-validation distribution (triple_similarity)
#   • Answer back-validation distribution (qa_similarity)
# and each STS-B bin: 2–3, 3–4, 4–5, 5
#
# Usage:
#   Rscript 07_w1_triple_vs_qa.R
#
# Inputs (same folder):
#   - triple_qa_similarities02.csv   (columns include: triple_similarity, qa_similarity)
#   - stsb_miniLM_cosines.csv        (columns: sentence1, sentence2, gold_score, bin, cosine)

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ---- files ---------------------------------------------------------------
csv_main <- "triple_qa_similarities02.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_main)) stop("Missing file: ", csv_main)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

# ---- load back-validation distributions ----------------------------------
df <- read_csv(csv_main, show_col_types = FALSE)

if (!all(c("triple_similarity","qa_similarity") %in% names(df))) {
  stop("triple_qa_similarities02.csv must contain columns: triple_similarity, qa_similarity")
}

vec_tri <- df$triple_similarity  |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()
vec_qa  <- df$qa_similarity      |> as.numeric() |> (\(x) x[is.finite(x)])() |> (\(x) pmin(pmax(x,0),1))()

if (length(vec_tri) == 0 && length(vec_qa) == 0) stop("No valid triple/qa similarity values after cleaning.")

# ---- load STS-B (recompute bins from gold_score to guarantee a '5' bin) --
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)

if (!all(c("gold_score","cosine") %in% names(stsb_raw))) {
  stop("stsb_miniLM_cosines.csv must contain columns: gold_score, cosine")
}

bin_from_gold <- function(g) {
  if (!is.finite(g)) return(NA_character_)
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

stsb <- stsb_raw %>%
  transmute(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin        = vapply(as.numeric(gold_score), bin_from_gold, character(1))
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score), !is.na(bin))

target_bins <- c("2–3","3–4","4–5","5")

# ---- W1 helper (quantile integral approximation) -------------------------
w1_quantile <- function(x, y, m = 2000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# ---- compute W1 for both distributions vs each bin -----------------------
make_row <- function(label, vec, bin_label) {
  ref <- stsb %>% filter(bin == bin_label) %>% pull(cosine)
  tibble(
    Comparison = sprintf("%s vs STS-B (%s)", label, bin_label),
    N_A = length(vec),
    N_B = length(ref),
    W1  = w1_quantile(vec, ref)
  )
}

rows <- list()
for (b in target_bins) {
  rows[[length(rows)+1]] <- make_row("Triple",  vec_tri, b)
  rows[[length(rows)+1]] <- make_row("Answer",  vec_qa,  b)
}
res_long <- bind_rows(rows)

# ---- pretty-print table ---------------------------------------------------
res_long$W1 <- round(res_long$W1, 5)
cat("\n1-Wasserstein distances: Triple / Answer vs STS-B bins (2–3, 3–4, 4–5, 5)\n\n")
print(kable(res_long, align = "lccc"))

# ---- (optional) also show in wide form by bin ----------------------------
wide <- res_long %>%
  mutate(Distr = ifelse(grepl("^Triple", Comparison), "Triple back-validation", "Answer back-validation"),
         Bin   = sub(".*\\((.*)\\).*", "\\1", Comparison)) %>%
  select(Distr, Bin, W1) %>%
  tidyr::pivot_wider(names_from = Bin, values_from = W1) %>%
  arrange(match(Distr, c("Triple back-validation","Answer back-validation")))

cat("\nWide view (W1 only):\n\n")
print(kable(wide, align = "lcccc"))