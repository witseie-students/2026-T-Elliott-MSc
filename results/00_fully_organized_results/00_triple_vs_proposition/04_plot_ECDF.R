#!/usr/bin/env Rscript
# 12_props_triples_vs_stsb_ecdf.R
#
# ECDF overlay for:
#   • STS-B bin 4–5 (gradient colour)
#   • STS-B bin 5   (gradient colour)
#   • Combined Propositions (blue)
#   • Combined Back-translated Triples (red)
#
# Now: thinner HD lines, Cairo anti-aliasing, consistent STS-B colours.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(ggplot2)
  library(scales)
})

# ── inputs ────────────────────────────────────────────────────────────────
csv_stsb  <- "stsb_miniLM_cosines.csv"
csv_props <- "propositions_combined.csv"
csv_trips <- "single_extraction.csv"
out_png   <- "04_props_triples_vs_stsb_ecdf.png"

if (!file.exists(csv_stsb))  stop("Missing file: ", csv_stsb)
if (!file.exists(csv_props)) stop("Missing file: ", csv_props)
if (!file.exists(csv_trips)) stop("Missing file: ", csv_trips)

# ── STS-B: (re)bin and keep 4–5 and 5 ─────────────────────────────────────
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)
bin_from_gold <- function(g) {
  if (g >= 4.999) return("5")    # robust exact 5.0 as separate bin
  if (g >= 4 && g < 5) return("4–5")
  if (g >= 3 && g < 4) return("3–4")
  if (g >= 2 && g < 3) return("2–3")
  if (g >= 1 && g < 2) return("1–2")
  return("0–1")
}

stsb <- stsb_raw %>%
  mutate(
    gold_score = as.numeric(gold_score),
    cosine     = pmin(pmax(as.numeric(cosine), 0), 1),
    bin_calc   = vapply(gold_score, bin_from_gold, character(1))
  ) %>%
  filter(is.finite(cosine), is.finite(gold_score)) %>%
  filter(bin_calc %in% c("4–5","5")) %>%
  transmute(group = paste0("STS-B (", bin_calc, ")"),
            cosine = cosine)

# ── Your datasets ─────────────────────────────────────────────────────────
df_props <- read_csv(csv_props, show_col_types = FALSE)
df_trips <- read_csv(csv_trips, show_col_types = FALSE)

vals_props <- df_props$combined_proposition_similarity |> as.numeric() |> pmin(1) |> pmax(0)
vals_trips <- df_trips$combined_similarity            |> as.numeric() |> pmin(1) |> pmax(0)

props <- tibble(group = "Combined Propositions",
                cosine = vals_props[is.finite(vals_props)])
trips <- tibble(group = "Combined Back-translated Triples",
                cosine = vals_trips[is.finite(vals_trips)])

df <- bind_rows(stsb, props, trips)

grp_levels <- c("STS-B (4–5)", "STS-B (5)",
                "Combined Propositions", "Combined Back-translated Triples")
df$group <- factor(df$group, levels = grp_levels, ordered = TRUE)

# ── colours ──────────────────────────────────────────────────────────────
# Gradient (consistent with your other figures)
anchor_cols <- c("#fbb4ae", "#fff2ae", "#b3e2cd")  # pastel R–A–M
grad_fun    <- colorRampPalette(anchor_cols)

summary_df <- df %>%
  group_by(group) %>%
  summarise(median = median(cosine), .groups = "drop")

cols_cont   <- grad_fun(1000)
col_for_val <- function(x) cols_cont[pmax(1, pmin(1000, round(x*999) + 1))]

group_cols  <- setNames(col_for_val(summary_df$median), summary_df$group)
group_cols["Combined Propositions"]            <- "#1f78b4"  # blue
group_cols["Combined Back-translated Triples"] <- "#e41a1c"  # red

# ── plot ECDFs (thin crisp lines) ─────────────────────────────────────────
p <- ggplot(df, aes(x = cosine, colour = group)) +
  stat_ecdf(geom = "step", linewidth = 0.7, lineend = "round") +  # thinner lines
  scale_x_continuous(
    limits = c(0, 1),
    breaks = seq(0, 1, 0.1),
    expand = c(0, 0)
  ) +
  scale_colour_manual(values = group_cols, name = NULL) +
  labs(
    x = "Cosine similarity",
    y = "Empirical CDF"
  ) +
  theme_bw(base_size = 11) +
  theme(
    plot.title       = element_text(hjust = 0.5, size = 13, family = "Times"),
    plot.subtitle    = element_text(hjust = 0.5, size = 10, family = "Times"),
    legend.title     = element_text(size = 10),
    legend.text      = element_text(size = 9),
    panel.grid.minor = element_blank()
  )

print(p)

# ── save (vector anti-aliasing) ──────────────────────────────────────────
ggsave(
  filename = out_png,
  plot     = p,
  width    = 200,   # mm
  height   = 80,    # mm
  units    = "mm",
  dpi      = 1200,  # super HD
  bg       = "white",
  type     = "cairo"
)

message("Saved ECDF figure to: ", out_png)