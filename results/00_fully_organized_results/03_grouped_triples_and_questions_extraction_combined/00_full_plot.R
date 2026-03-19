# 00_full_plot.R (HD version)
#
# Panels (top → bottom):
#   1) Density overlay — Triple (blue) & Answer (red)
#   2) Combined horizontal box & whiskers containing:
#        - Triple (blue) [TOP]
#        - Question–Answer (red)
#        - STS-B bins (3–4, 4–5, 5) [BOTTOM]
#
# Inputs (same folder):
#   - combined_from_triples_similarities2.csv
#       (paragraph_id, proposition_id, n_triples,
#        triple_combined_similarity, qa_combined_similarity)
#   - stsb_miniLM_cosines.csv  (gold_score, cosine)
#
# Outputs:
#   - 00_full_plot.png
#   - 00_full_plot_stats.csv
#
# install.packages(c("readr","dplyr","ggplot2","patchwork","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(knitr)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_main <- "combined_from_triples_similarities2.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

out_png  <- "04_05_4_FULL_RESULTS_COMBINED_TRIPLES_v2.png"
out_csv  <- "00_full_plot_stats.csv"
adjust_k <- 0.8  # KDE bandwidth

stopifnot(file.exists(csv_main), file.exists(csv_stsb))

# ── load main data ────────────────────────────────────────────────────────
need_cols <- c("paragraph_id","proposition_id","n_triples",
               "triple_combined_similarity","qa_combined_similarity")

df <- read_csv(csv_main, show_col_types = FALSE)
if (!all(need_cols %in% names(df))) {
  stop("combined_from_triples_similarities2.csv must contain: ",
       paste(need_cols, collapse=", "))
}

df <- df %>%
  mutate(
    triple_combined_similarity = pmin(pmax(as.numeric(triple_combined_similarity), 0), 1),
    qa_combined_similarity     = pmin(pmax(as.numeric(qa_combined_similarity), 0), 1)
  )

tri_vals <- df %>% filter(!is.na(triple_combined_similarity)) %>% pull(triple_combined_similarity)
qa_vals  <- df %>% filter(!is.na(qa_combined_similarity))     %>% pull(qa_combined_similarity)

if (length(tri_vals) == 0 & length(qa_vals) == 0) {
  stop("No valid similarity values found in combined_from_triples_similarities2.csv")
}

# ── summary stats (and write CSV) ─────────────────────────────────────────
get_mode_kde <- function(v) {
  if (length(v) < 2) return(NA_real_)
  d <- density(v, from = 0, to = 1)
  d$x[which.max(d$y)]
}

summ <- tibble(
  series   = c("Triple back-validation", "Question–Answer back-validation"),
  n        = c(length(tri_vals), length(qa_vals)),
  mean     = c(mean(tri_vals),  mean(qa_vals)),
  median   = c(median(tri_vals), median(qa_vals)),
  q1       = c(quantile(tri_vals, 0.25), quantile(qa_vals, 0.25)),
  q3       = c(quantile(tri_vals, 0.75), quantile(qa_vals, 0.75)),
  sd       = c(sd(tri_vals), sd(qa_vals)),
  min      = c(min(tri_vals), min(qa_vals)),
  max      = c(max(tri_vals), max(qa_vals)),
  mode_kde = c(get_mode_kde(tri_vals), get_mode_kde(qa_vals))
)

write_csv(summ %>% mutate(across(where(is.numeric), ~round(.x, 6))), out_csv)

cat("\nSummary metrics (Triple vs Answer back-validation)\n\n")
print(knitr::kable(summ %>% mutate(across(where(is.numeric), ~round(.x, 4))),
                   align = "lccccccccc"))

# ── colours & linetypes ───────────────────────────────────────────────────
col_tri <- "#1f77b4"  # blue
col_ans <- "#d62728"  # red

fills_density <- c("Triple back-validation" = col_tri,
                   "Question–Answer back-validation" = col_ans)
ltys_density  <- c("Triple back-validation" = "solid",
                   "Question–Answer back-validation" = "22")  # short-dash

legend_order <- c("Triple back-validation", "Question–Answer back-validation")

# ── density overlay (HD tweaks: thinner lines, slightly lighter fill) ─────
df_dens <- bind_rows(
  tibble(series = "Triple back-validation",            value = tri_vals),
  tibble(series = "Question–Answer back-validation",   value = qa_vals)
) %>% mutate(series = factor(series, levels = legend_order, ordered = TRUE))

summ_density <- summ %>%
  select(series, mean, median) %>%
  mutate(series = factor(series, levels = legend_order, ordered = TRUE))

p_dens <- ggplot(df_dens, aes(x = value)) +
  geom_density(aes(fill = series, linetype = series),
               colour = "black", linewidth = 0.35, alpha = 0.32, adjust = adjust_k) +
  geom_vline(data = summ_density, aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.4, show.legend = FALSE) +
  geom_vline(data = summ_density, aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.4, show.legend = FALSE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills_density, breaks = legend_order, name = NULL) +
  scale_linetype_manual(values = ltys_density, breaks = legend_order, name = NULL) +
  scale_colour_manual(values = fills_density, guide = "none") +
  theme_bw(base_size = 12) +
  theme(
    text               = element_text(family = "Times"),
    panel.grid.minor   = element_blank(),
    panel.grid.major.x = element_blank(),
    legend.position    = "top"
  )

# ── STS-B bins (3–4, 4–5, 5) for box panel ───────────────────────────────
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
  )

stsb_bins <- stsb %>%
  filter(bin %in% c("3–4","4–5","5")) %>%
  mutate(series = paste0("STS ", bin)) %>%
  select(series, value = cosine)

# R–A–G palette keyed by each bin’s median
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
grad_fun     <- colorRampPalette(c(pastel_red, pastel_amber, pastel_mint))
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_meds <- stsb_bins %>% group_by(series) %>%
  summarise(median = median(value), .groups = "drop")
stsb_cols <- setNames(col_for_val(stsb_meds$median), stsb_meds$series)

# ── combined box data (Triples, Answers, STS bins) ────────────────────────
df_box <- bind_rows(
  tibble(series = "Triple back-validation",          value = tri_vals),
  tibble(series = "Question–Answer back-validation", value = qa_vals),
  stsb_bins
) %>% filter(!is.na(value))

# Desired vertical order (top → bottom): Triples, Answers, STS 5, 4–5, 3–4
y_levels <- c("Triple back-validation",
              "Question–Answer back-validation",
              "STS 5", "STS 4–5", "STS 3–4")
df_box$series <- factor(df_box$series, levels = y_levels, ordered = TRUE)

fills_all <- c(
  "Triple back-validation"          = col_tri,
  "Question–Answer back-validation" = col_ans,
  stsb_cols
)

p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18,
               outlier.shape = 16, outlier.size = 0.85,
               linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0),
                     name = "Cosine similarity (0–1)") +
  scale_y_discrete(limits = rev(y_levels), labels = NULL) +
  scale_fill_manual(values = fills_all, guide = "none") +
  labs(subtitle = "Box & whiskers: Triples (blue), Answers (red), and STS-B bins 3, 4 & 5 (green)") +
  theme_bw(base_size = 12) +
  theme(
    text               = element_text(family = "Times"),
    plot.subtitle      = element_text(hjust = 0.5),
    panel.grid.minor   = element_blank(),
    panel.grid.major.x = element_blank(),
    axis.ticks.y       = element_blank()
  )

# ── assemble & save (HD: larger size + higher DPI) ────────────────────────
final_plot <- p_dens / p_box +
  plot_layout(heights = c(2.9, 1.5))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = 240,  # mm (wider canvas)
  height   = 185,  # mm (taller for clarity)
  units    = "mm",
  dpi      = 1200, # extra crisp
  bg       = "white"
)

message("Saved figure to: ", out_png)
message("Wrote stats to:  ", out_csv)