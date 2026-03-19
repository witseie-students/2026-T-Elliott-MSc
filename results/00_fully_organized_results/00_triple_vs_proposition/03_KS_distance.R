#!/usr/bin/env Rscript
# 11_ks_vs_stsb_bins.R
#
# Compute Kolmogorov–Smirnov (two-sample) distances (D) between:
#   • Combined Propositions (propositions_combined.csv)
#   • Combined Back-translated Triples (single_extraction.csv)
# and STS-B bins: 3–4, 4–5, 5 from stsb_miniLM_cosines.csv
#
# Outputs:
#   - ks_vs_stsb_bins.csv           (tidy results with D and p)
#   - ks_vs_stsb_bins_table.tex     (LaTeX table with D only, 4 d.p.)
#   - also prints the LaTeX table to the terminal
#
# Run:  Rscript 11_ks_vs_stsb_bins.R
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
out_csv   <- "ks_vs_stsb_bins.csv"
out_tex   <- "ks_vs_stsb_bins_table.tex"

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
  if (g >= 4.999) return("5")      # robust exact 5.0
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

# keep only target bins 3–4, 4–5, 5
bins_target <- c("3–4", "4–5", "5")
stsb_bins <- stsb_bins |> filter(bin %in% bins_target)

cat("\nSTS-B counts for target bins:\n")
print(stsb_bins |> count(bin) |> arrange(bin))

# ── KS helper (D and p) ──────────────────────────────────────────────────
ks_two_sample <- function(x, y) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(c(D = NA_real_, p = NA_real_))
  kt <- suppressWarnings(stats::ks.test(x, y, exact = FALSE))  # large n → asymptotic p
  c(D = unname(kt$statistic), p = unname(kt$p.value))
}

# ── compute comparisons ──────────────────────────────────────────────────
rows <- list()
for (b in bins_target) {
  y <- stsb_bins |> filter(bin == b) |> pull(cosine)

  # Propositions vs STS-B bin
  ks_p <- ks_two_sample(vals_props, y)
  rows[[length(rows)+1]] <- data.frame(
    Which       = "Combined Propositions",
    Bin         = b,
    N_x         = length(vals_props),
    N_y         = length(y),
    D           = ks_p["D"],
    p           = ks_p["p"],
    stringsAsFactors = FALSE
  )

  # Triples vs STS-B bin
  ks_t <- ks_two_sample(vals_trips, y)
  rows[[length(rows)+1]] <- data.frame(
    Which       = "Combined Back-translated Triples",
    Bin         = b,
    N_x         = length(vals_trips),
    N_y         = length(y),
    D           = ks_t["D"],
    p           = ks_t["p"],
    stringsAsFactors = FALSE
  )
}
res <- do.call(rbind, rows)

# ── print tidy table (console) ───────────────────────────────────────────
res_print <- res |>
  arrange(Which, factor(Bin, levels = bins_target)) |>
  mutate(
    D = round(as.numeric(D), 4),
    p = formatC(p, format = "e", digits = 3)
  )
cat("\nKolmogorov–Smirnov distances (D) vs STS-B bins (3–4, 4–5, 5)\n")
cat("D ranges in [0,1]; larger D ⇒ greater distributional difference.\n\n")
print(kable(res_print, align = "lcrrcc",
            col.names = c("Distribution","Bin","N_x","N_y","D","p")))
cat("\n")

# ── write raw (unrounded) results to CSV ─────────────────────────────────
write_csv(res, out_csv)
cat("Saved raw results to: ", out_csv, "\n")

# ── build LaTeX table (booktabs + makecell) with D only, 4 d.p. ─────────
# Extract rows in the desired order
get_D <- function(w, b) {
  d <- res %>% filter(Which == w, Bin == b) %>% pull(D)
  if (length(d) == 0) return(NA_real_) else return(d[1])
}
D_props_34 <- get_D("Combined Propositions", "3–4")
D_props_45 <- get_D("Combined Propositions", "4–5")
D_props_5  <- get_D("Combined Propositions", "5")
D_trip_34  <- get_D("Combined Back-translated Triples", "3–4")
D_trip_45  <- get_D("Combined Back-translated Triples", "4–5")
D_trip_5   <- get_D("Combined Back-translated Triples", "5")

fmt <- function(x) ifelse(is.na(x), "--", formatC(x, format = "f", digits = 4))
lp <- sprintf("\\begin{table}[H]
  \\centering
  \\caption{Kolmogorov--Smirnov distance ($D$) between abstract-level extractions of back-validated Propositions and Triples and STS-B bins.}
  \\label{tab:ks_vs_stsb_triple_prop}
  \\begin{tabular}{@{}lccc@{}}
    \\toprule
    \\textbf{Distribution} & \\textbf{Bin 3--4} & \\textbf{Bin 4--5} & \\textbf{Bin 5} \\\\
    \\midrule
    \\makecell[l]{Combined Propositions} & %s & %s & %s \\\\
    \\makecell[l]{Combined Back-translated Triples} & %s & %s & %s \\\\
    \\bottomrule
  \\end{tabular}
\\end{table}
", fmt(D_props_34), fmt(D_props_45), fmt(D_props_5),
   fmt(D_trip_34),  fmt(D_trip_45),  fmt(D_trip_5))

cat("\nLaTeX table (copy/paste into your thesis):\n\n")
cat(lp, "\n")

writeLines(lp, out_tex)
cat("\nSaved LaTeX table to: ", out_tex, "\n")