#!/usr/bin/env Rscript
# 10_ttest_vs_stsb_bins.R
#
# Compute Welch t-test p-values comparing:
#   • Propositions (propositions_combined.csv)
#   • Triple-Sentences (single_extraction.csv)
# against STS-B bins: 4–5 and 5 from stsb_miniLM_cosines.csv
#
# Output:
#   - ttest_vs_stsb_bins.csv  (results table)
#   - results also printed to terminal
#
# Run:
#   Rscript 10_ttest_vs_stsb_bins.R
#
# Requires:
#   install.packages(c("readr","dplyr","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(knitr)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_props <- "propositions_combined.csv"
csv_trips <- "single_extraction.csv"
csv_stsb  <- "stsb_miniLM_cosines.csv"
out_csv   <- "ttest_vs_stsb_bins.csv"

if (!file.exists(csv_props)) stop("Missing file: ", csv_props)
if (!file.exists(csv_trips)) stop("Missing file: ", csv_trips)
if (!file.exists(csv_stsb))  stop("Missing file: ", csv_stsb)

# ── load your datasets ───────────────────────────────────────────────────
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
  stop("No valid values in propositions or triple-sentences after cleaning.")
}

# ── load STS-B and (re)bin from gold_score ───────────────────────────────
stsb <- read_csv(csv_stsb, show_col_types = FALSE)
if (!all(c("gold_score","cosine") %in% names(stsb))) {
  stop(csv_stsb, " must contain columns: gold_score, cosine (plus sentence1, sentence2, bin optional)")
}

bin_from_gold <- function(g) {
  if (g >= 4.999) return("5")      # robust 5.0
  if (g >= 4 && g < 5) return("4–5")
  if (g >= 3 && g < 4) return("3–4")
  if (g >= 2 && g < 3) return("2–3")
  if (g >= 1 && g < 2) return("1–2")
  return("0–1")
}

stsb_bins <- stsb |>
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = as.numeric(cosine),
    bin_calc   = vapply(gold_score, bin_from_gold, character(1))
  ) |>
  filter(is.finite(cosine), is.finite(gold_score)) |>
  mutate(cosine = pmin(pmax(cosine, 0), 1)) |>
  select(bin = bin_calc, cosine)

# keep only target bins 4–5 and 5
bins_target <- c("4–5", "5")
stsb_bins <- stsb_bins |> filter(bin %in% bins_target)

cat("\nSTS-B counts for target bins:\n")
print(stsb_bins |> count(bin) |> arrange(bin))

# ── Welch t-test helper (returns both two-sided and directional p) ───────
ttest_all <- function(x, y) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(rep(NA_real_, 7))
  tt_2s <- t.test(x, y, var.equal = FALSE, alternative = "two.sided")
  tt_lt <- t.test(x, y, var.equal = FALSE, alternative = "less")    # H1: mean_x < mean_y
  tt_gt <- t.test(x, y, var.equal = FALSE, alternative = "greater") # H1: mean_x > mean_y
  c(t      = unname(tt_2s$statistic),
    df     = unname(tt_2s$parameter),
    p_two  = unname(tt_2s$p.value),
    p_less = unname(tt_lt$p.value),
    p_grea = unname(tt_gt$p.value),
    mean_x = mean(x), mean_y = mean(y))
}

# ── assemble comparisons ─────────────────────────────────────────────────
rows <- list()

for (b in bins_target) {
  y <- stsb_bins |> filter(bin == b) |> pull(cosine)

  # Propositions vs STS-B bin
  stats_p <- ttest_all(vals_props, y)
  rows[[length(rows)+1]] <- data.frame(
    Comparison = sprintf("Propositions vs STS-B (%s)", b),
    N_x = length(vals_props), N_y = length(y),
    Mean_x = stats_p["mean_x"], Mean_y = stats_p["mean_y"],
    Diff   = stats_p["mean_x"] - stats_p["mean_y"],
    t      = stats_p["t"], df = stats_p["df"],
    p_two  = stats_p["p_two"],
    p_less = stats_p["p_less"],  # H1: props < STS-B bin
    p_grea = stats_p["p_grea"],  # H1: props > STS-B bin
    stringsAsFactors = FALSE
  )

  # Triple-Sentences vs STS-B bin
  stats_t <- ttest_all(vals_trips, y)
  rows[[length(rows)+1]] <- data.frame(
    Comparison = sprintf("Triple-Sentences vs STS-B (%s)", b),
    N_x = length(vals_trips), N_y = length(y),
    Mean_x = stats_t["mean_x"], Mean_y = stats_t["mean_y"],
    Diff   = stats_t["mean_x"] - stats_t["mean_y"],
    t      = stats_t["t"], df = stats_t["df"],
    p_two  = stats_t["p_two"],
    p_less = stats_t["p_less"],  # H1: triples < STS-B bin
    p_grea = stats_t["p_grea"],  # H1: triples > STS-B bin
    stringsAsFactors = FALSE
  )
}

res <- do.call(rbind, rows)

# ── pretty print & save ──────────────────────────────────────────────────
res_print <- res |>
  mutate(
    Mean_x = round(Mean_x, 4),
    Mean_y = round(Mean_y, 4),
    Diff   = round(Diff, 4),
    t      = round(as.numeric(t), 3),
    df     = round(as.numeric(df), 1),
    p_two  = formatC(p_two,  format = "e", digits = 3),
    p_less = formatC(p_less, format = "e", digits = 3),
    p_grea = formatC(p_grea, format = "e", digits = 3)
  )

cat("\nWelch t-tests (two-sided and directional one-tailed p-values)\n\n")
print(kable(res_print, align = "lrrrrrrrrrr",
            col.names = c("Comparison","N_x","N_y","Mean_x","Mean_y","Diff",
                          "t","df","p_two","p_less","p_grea")))
cat("\n")

# Also write raw (unrounded) values to CSV for reproducibility
write_csv(res, out_csv)
cat("Saved results to: ", out_csv, "\n")