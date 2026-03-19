# 00_plot.R (HD version, STS bins reversed + new subtitle)
#
# Panels (top → bottom):
#   1) Density overlay (Propositions = blue, Coreferences = red, Recombined Triples = purple)
#   2) One combined horizontal box & whiskers:
#        - (TOP) STS 3–4, STS 4–5, STS 5, Recombined Triples, Coreferences, Propositions (BOTTOM)
#
# Inputs (same folder):
#   - combined_paragraph_from_triples.csv
#       Columns: paragraph_id,
#                recombined_triple_similarity,
#                combined_proposition_similarity,
#                combined_coref_similarity
#   - stsb_miniLM_cosines.csv  (gold_score, cosine)
#
# Output:
#   - 02_paragraph_level.png
#
# install.packages(c("readr","dplyr","ggplot2","patchwork"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2); library(patchwork)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_main <- "combined_paragraph_from_triples.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"
out_png  <- "04_07_DENSITY_PLOT_OVERALL_RESULTS_v2.png"

stopifnot(file.exists(csv_main), file.exists(csv_stsb))

# ── load & tidy main data ─────────────────────────────────────────────────
need_cols <- c("paragraph_id",
               "recombined_triple_similarity",
               "combined_proposition_similarity",
               "combined_coref_similarity")

df <- read_csv(csv_main, show_col_types = FALSE)
if (!all(need_cols %in% names(df))) {
  stop("combined_paragraph_from_triples.csv must contain: ",
       paste(need_cols, collapse=", "))
}

df_long <- bind_rows(
  df %>% transmute(series = "Propositions",
                   value  = as.numeric(combined_proposition_similarity)),
  df %>% transmute(series = "Coreferences",
                   value  = as.numeric(combined_coref_similarity)),
  df %>% transmute(series = "Recombined Triples",
                   value  = as.numeric(recombined_triple_similarity))
) %>%
  filter(!is.na(value)) %>%
  mutate(value = pmin(pmax(value, 0), 1))

if (nrow(df_long) == 0) stop("No valid values to plot after cleaning.")

# Legend / display order for the THREE main series
legend_order <- c("Propositions", "Coreferences", "Recombined Triples")
df_long$series <- factor(df_long$series, levels = legend_order, ordered = TRUE)

# Summary lines for density (means & medians)
summ_lines <- df_long %>%
  group_by(series) %>%
  summarise(mean = mean(value), median = median(value), .groups = "drop")

# ── STS-B bins (3–4, 4–5, 5) ─────────────────────────────────────────────
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
  filter(!is.na(gold_score), !is.na(cosine)) %>%
  mutate(
    cosine = pmin(pmax(as.numeric(cosine), 0), 1),
    bin = case_when(
      gold_score == 5                  ~ "5",
      gold_score >= 4 & gold_score < 5 ~ "4–5",
      gold_score >= 3 & gold_score < 4 ~ "3–4",
      gold_score >= 2 & gold_score < 3 ~ "2–3",
      gold_score >= 1 & gold_score < 2 ~ "1–2",
      TRUE                             ~ "0–1"
    )
  ) %>%
  filter(bin %in% c("3–4","4–5","5"))

stsb_bins <- stsb %>%
  transmute(series = paste0("STS ", bin), value = cosine)

# R–A–G palette keyed to each bin's median
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
grad_fun     <- colorRampPalette(c(pastel_red, pastel_amber, pastel_mint))
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_meds <- stsb_bins %>% group_by(series) %>%
  summarise(median = median(value), .groups = "drop")
stsb_cols <- setNames(col_for_val(stsb_meds$median), stsb_meds$series)

# ── colours & linetypes (Recombined Triples now PURPLE) ──────────────────
col_props <- "#1f77b4"  # blue
col_coref <- "#d62728"  # red
col_tri   <- "#9467bd"  # purple

fills_main <- c("Propositions"        = col_props,
                "Coreferences"        = col_coref,
                "Recombined Triples"  = col_tri)

ltys_main  <- c("Propositions"        = "solid",
                "Coreferences"        = "22",   # short-dash
                "Recombined Triples"  = "44")   # long-dash

# ── density panel (thin lines) ────────────────────────────────────────────
p_dens <- ggplot(df_long, aes(x = value)) +
  geom_density(aes(fill = series, linetype = series),
               colour    = "black",
               linewidth = 0.35,   # thinner outline
               alpha     = 0.35,
               adjust    = 0.8) +
  geom_vline(data = summ_lines,
             aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.4, show.legend = FALSE) +
  geom_vline(data = summ_lines,
             aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.4, show.legend = FALSE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills_main, breaks = legend_order, name = NULL) +
  scale_linetype_manual(values = ltys_main, breaks = legend_order, name = NULL) +
  scale_colour_manual(values = fills_main, guide = "none") +
  theme_bw(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    legend.position  = "top"
  ) 

# ── combined box & whiskers (STS bins reversed; full order reversed) ─────
df_box <- bind_rows(
  df_long,
  stsb_bins
) %>% filter(!is.na(value))

# Desired TOP → BOTTOM order:
#   STS 3–4, STS 4–5, STS 5, Recombined Triples, Coreferences, Propositions
y_levels_rev <- c("STS 3–4", "STS 4–5", "STS 5",
                  "Recombined Triples", "Coreferences", "Propositions")
df_box$series <- factor(df_box$series, levels = y_levels_rev, ordered = TRUE)

fills_all <- c(fills_main, stsb_cols)

p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18,
               outlier.shape = 16, outlier.size = 0.9,
               linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0),
                     name = "Cosine similarity (0–1)") +
  scale_y_discrete(limits = y_levels_rev, labels = NULL) +
  scale_fill_manual(values = fills_all, guide = "none") +
  labs(subtitle = "Box & whiskers: Propositions (blue), Coreferences (red), Triple-sentence (purple), and STS-B bins 3, 4 & 5 (green)") +
  theme_bw(base_size = 11) +
  theme(
    plot.subtitle    = element_text(hjust = 0.5),
    panel.grid.minor = element_blank(),
    axis.ticks.y     = element_blank()
  )

# ── assemble & save (HD: larger size + higher DPI) ────────────────────────
final_plot <- p_dens / p_box +
  plot_layout(heights = c(2.6, 1.5))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = 240,  # mm
  height   = 190,  # mm
  units    = "mm",
  dpi      = 1200, # crisp lines (HD)
  bg       = "white"
)

message("Saved figure to: ", out_png)