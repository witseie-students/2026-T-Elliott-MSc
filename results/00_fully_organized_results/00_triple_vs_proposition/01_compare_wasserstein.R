# 07_wasserstein_vs_stsb_bins.R
#
# Compute 1-Wasserstein distances between:
#   • Combined propositions (propositions_combined.csv)
#   • Combined Triple-Sentences (single_extraction.csv)
# and STS-B bins 3–4, 4–5, 5 from stsb_miniLM_cosines.csv
#
# Run:  Rscript 07_wasserstein_vs_stsb_bins.R
#
# install.packages(c("readr","dplyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# --- files -----------------------------------------------------------------
csv_props <- "propositions_combined.csv"
csv_trips <- "single_extraction.csv"
csv_stsb  <- "stsb_miniLM_cosines.csv"

if (!file.exists(csv_props)) stop("Missing file: ", csv_props)
if (!file.exists(csv_trips)) stop("Missing file: ", csv_trips)
if (!file.exists(csv_stsb))  stop("Missing file: ", csv_stsb)

# --- load paragraph-level distributions -----------------------------------
df_props <- read_csv(csv_props, show_col_types = FALSE)
df_trips <- read_csv(csv_trips, show_col_types = FALSE)

need_p <- c("paragraph_id", "combined_proposition_similarity")
need_t <- c("paragraph_id", "combined_similarity")
if (!all(need_p %in% names(df_props))) stop(csv_props, " must contain: ", paste(need_p, collapse=", "))
if (!all(need_t %in% names(df_trips))) stop(csv_trips, " must contain: ", paste(need_t, collapse=", "))

vals_props <- df_props$combined_proposition_similarity |> as.numeric() |> pmin(1) |> pmax(0)
vals_trips <- df_trips$combined_similarity            |> as.numeric() |> pmin(1) |> pmax(0)

vals_props <- vals_props[is.finite(vals_props)]
vals_trips <- vals_trips[is.finite(vals_trips)]

if (length(vals_props) == 0 || length(vals_trips) == 0) {
  stop("No valid values in one of the paragraph-level files after cleaning.")
}

# --- load STS-B and (re)bin ------------------------------------------------
stsb <- read_csv(csv_stsb, show_col_types = FALSE)
if (!all(c("gold_score","cosine") %in% names(stsb))) {
  stop(csv_stsb, " must contain columns: gold_score, cosine (plus sentence1, sentence2, bin optional)")
}

# Robust binning: treat true 5.0 as separate "5"
bin_from_gold <- function(g) {
  if (g >= 4.999) return("5")
  if (g >= 4   && g < 5) return("4–5")
  if (g >= 3   && g < 4) return("3–4")
  if (g >= 2   && g < 3) return("2–3")
  if (g >= 1   && g < 2) return("1–2")
  return("0–1")
}

stsb <- stsb |>
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin_calc   = vapply(gold_score, bin_from_gold, character(1))
  ) |>
  filter(is.finite(cosine), is.finite(gold_score)) |>
  mutate(cosine = pmin(pmax(cosine, 0), 1))

# Keep only bins of interest
bins_target <- c("3–4","4–5","5")
stsb_bins <- stsb |>
  filter(bin_calc %in% bins_target) |>
  select(bin = bin_calc, cosine)

# Quick counts
cat("\nSTS-B counts for target bins:\n")
print(stsb_bins |> count(bin) |> arrange(bin))

# --- W1 via quantile integral ---------------------------------------------
# W1(F,G) = ∫_0^1 |F^{-1}(t) − G^{-1}(t)| dt  (approx by averaging abs diff of quantiles)
w1_quantile <- function(x, y, m = 1000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# --- compute distances: props & trips vs each bin --------------------------
rows <- list()
for (b in bins_target) {
  y <- stsb_bins |> filter(bin == b) |> pull(cosine)
  rows[[length(rows)+1]] <- data.frame(
    Comparison = sprintf("Propositions vs STS-B (%s)", b),
    N_A        = length(vals_props),
    N_B        = length(y),
    W1         = w1_quantile(vals_props, y),
    stringsAsFactors = FALSE
  )
  rows[[length(rows)+1]] <- data.frame(
    Comparison = sprintf("Triple-Sentences vs STS-B (%s)", b),
    N_A        = length(vals_trips),
    N_B        = length(y),
    W1         = w1_quantile(vals_trips, y),
    stringsAsFactors = FALSE
  )
}
res <- do.call(rbind, rows)

# --- print tidy table ------------------------------------------------------
cat("\n1-Wasserstein distances (smaller = more similar distributions)\n\n")
res_print <- res |>
  mutate(W1 = round(W1, 5))
print(kable(res_print, align = "lccc"))
cat("\n")