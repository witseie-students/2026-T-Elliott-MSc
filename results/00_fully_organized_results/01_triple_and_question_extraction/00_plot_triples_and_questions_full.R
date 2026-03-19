# 02_triple_qa_overlay_combined_box_with_stsb.R
#
# Top:    Overlayed density curves (Triple = blue, Q&A = red) with mean/median lines
# Middle: Single combined horizontal box plot including:
#          • Triple back-validation (blue)
#          • Q&A back-validation (red)
#          • STS-B bins 2–3, 3–4, 4–5, 5 (R–A–G by each bin median)
#
# Inputs:
#   - quad_qa_similarities.csv  (paragraph_id, proposition_id, quad_index, triple_similarity, qa_similarity)
#   - stsb_miniLM_cosines.csv   (gold_score, cosine)
#
# Outputs:
#   - 02_triple_qa_overlay_combined_box_with_stsb.png
#   - 02_triple_qa_overlay_combined_box_with_stsb_stats.csv
#
# install.packages(c("readr","dplyr","ggplot2","patchwork","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(knitr)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_data <- "triple_qa_similarities02.csv"
csv_stsb <- "stsb_miniLM_cosines_no_bin5.csv"

out_png <- "04_04_triple_density_QA_pairs_v2.png"
out_csv <- "02_triple_qa_overlay_combined_box_with_stsb_stats.csv"

stopifnot(file.exists(csv_data), file.exists(csv_stsb))

# ── load & tidy main (Triple / Q&A) ───────────────────────────────────────
df <- read_csv(csv_data, show_col_types = FALSE)
need_cols <- c("paragraph_id","proposition_id","quad_index","triple_similarity","qa_similarity")
if (!all(need_cols %in% names(df))) {
  stop("quad_qa_similarities.csv must contain: ", paste(need_cols, collapse=", "))
}

df <- df %>%
  mutate(
    triple_similarity = as.numeric(triple_similarity),
    qa_similarity     = as.numeric(qa_similarity)
  ) %>%
  filter(!is.na(triple_similarity) | !is.na(qa_similarity)) %>%
  mutate(
    triple_similarity = pmin(pmax(triple_similarity, 0), 1),
    qa_similarity     = pmin(pmax(qa_similarity, 0), 1)
  )

tri_vals <- df %>% filter(!is.na(triple_similarity)) %>% pull(triple_similarity)
qa_vals  <- df %>% filter(!is.na(qa_similarity))     %>% pull(qa_similarity)
if (length(tri_vals) == 0 & length(qa_vals) == 0) stop("No valid similarity values to plot.")

# ── summary (Triple / Q&A) & CSV writer scaffold ──────────────────────────
get_mode_kde <- function(v) {
  if (length(v) < 2) return(NA_real_)
  d <- density(v, from = 0, to = 1)
  d$x[which.max(d$y)]
}

summ_main <- tibble(
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

# ── STS-B: load, bin, select 2–3/3–4/4–5/5, color by median ──────────────
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)

stsb_df <- stsb_raw %>%
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
    ),
    bin = factor(bin, levels = c("0–1","1–2","2–3","3–4","4–5","5"), ordered = TRUE)
  )

stsb_sel <- stsb_df %>%
  filter(bin %in% c("2–3","3–4","4–5","5")) %>%
  droplevels()

# R–A–G gradient for STS-B bins by MEDIAN
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
anchor_cols  <- c(pastel_red, pastel_amber, pastel_mint)
grad_fun     <- colorRampPalette(anchor_cols)
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_stats <- stsb_sel %>%
  group_by(series = paste0("STS-B ", as.character(bin))) %>%
  summarise(
    n        = n(),
    mean     = mean(cosine),
    median   = median(cosine),
    q1       = quantile(cosine, 0.25),
    q3       = quantile(cosine, 0.75),
    sd       = sd(cosine),
    min      = min(cosine),
    max      = max(cosine),
    mode_kde = get_mode_kde(cosine),
    .groups  = "drop"
  )

# Color map for STS-B series by MEDIAN
stsb_fill_map <- setNames(col_for_val(stsb_stats$median), stsb_stats$series)

# ── combined stats table (write CSV) ───────────────────────────────────────
stats_out <- bind_rows(
  summ_main,
  stsb_stats
) %>% mutate(across(where(is.numeric), ~round(.x, 4)))

write_csv(stats_out, out_csv)

cat("\nSummary metrics (Triple / Q&A / STS-B bins)\n\n")
print(knitr::kable(stats_out, align = "lccccccccc"))

# ── long data for plotting ────────────────────────────────────────────────
# DENSITY (only Triple & Q&A)
df_dens <- bind_rows(
  tibble(metric = "Triple back-validation",          value = tri_vals),
  tibble(metric = "Question–Answer back-validation", value = qa_vals)
) %>% filter(!is.na(value))

df_dens$metric <- factor(df_dens$metric,
                         levels = c("Triple back-validation",
                                    "Question–Answer back-validation"),
                         ordered = TRUE)

summary_dens <- df_dens %>%
  group_by(metric) %>%
  summarise(mean = mean(value), median = median(value), .groups = "drop")

# BOX: combine Triple/Q&A + STS-B into one panel
df_box_main <- df_dens %>% rename(series = metric)
df_box_stsb <- stsb_sel %>% transmute(series = paste0("STS-B ", as.character(bin)), value = cosine)

# Order: put Triple/Q&A first, then STS-B bins (5, 4–5, 3–4, 2–3)
series_levels <- c("Triple back-validation",
                   "Question–Answer back-validation",
                   "STS-B 5", "STS-B 4–5", "STS-B 3–4", "STS-B 2–3")

df_box <- bind_rows(df_box_main, df_box_stsb) %>%
  filter(!is.na(value)) %>%
  mutate(series = factor(series, levels = series_levels, ordered = TRUE))

# ── colours ───────────────────────────────────────────────────────────────
fills_density <- c("Triple back-validation"          = "#1f77b4",
                   "Question–Answer back-validation" = "#d62728")

fills_box <- c(
  fills_density,
  stsb_fill_map  # STS-B series names already prefixed "STS-B ..."
)

# ── overlay density (top) ─────────────────────────────────────────────────
p_dens <- ggplot(df_dens, aes(x = value)) +
  geom_density(aes(fill = metric),
               colour    = "black",
               linewidth = 0.5,
               alpha     = 0.35,
               adjust    = 0.8) +
  geom_vline(data = summary_dens,
             aes(xintercept = mean, colour = metric),
             linetype = "dashed", linewidth = 0.6, show.legend = FALSE) +
  geom_vline(data = summary_dens,
             aes(xintercept = median, colour = metric),
             linetype = "dotted", linewidth = 0.6, show.legend = FALSE) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0), name = NULL) +
  scale_y_continuous(expand = c(0, 0), name = "Density") +
  scale_fill_manual(values = fills_density, name = "Distribution") +
  scale_colour_manual(values = fills_density, guide = "none") +
  theme_bw(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    legend.position  = "top"
  )

# ── single combined horizontal box plot (middle) ──────────────────────────
p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18,
               outlier.shape = 16, outlier.size = 0.9,
               linewidth = 0.35) +
  # Mean/median lines only for Triple/Q&A (optional: could add for STS-B too)
  geom_vline(data = summary_dens %>% rename(series = metric),
             aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.5, show.legend = FALSE) +
  geom_vline(data = summary_dens %>% rename(series = metric),
             aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.5, show.legend = FALSE) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0),
                     name = "Cosine similarity (0–1)") +
  scale_y_discrete(limits = rev(series_levels), labels = NULL) +
  scale_fill_manual(values = fills_box, guide = "none") +
  scale_colour_manual(values = fills_density, guide = "none") +
  labs(subtitle = "Combined box and whiskers: Triple-Sentence (blue) • Question-Answer (red) • STS-B bins (2,3,4,5)") +
  theme_bw(base_size = 11) +
  theme(
    plot.subtitle    = element_text(hjust = 0.5),
    panel.grid.minor = element_blank(),
    axis.ticks.y     = element_blank()
  )

# ── assemble & save ───────────────────────────────────────────────────────
final_plot <- p_dens / p_box +
  plot_layout(heights = c(2, 2))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = 200,   # mm
  height   = 170,   # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved figure to: ", out_png)
message("Wrote stats to:  ", out_csv)