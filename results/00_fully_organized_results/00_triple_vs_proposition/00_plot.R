# 00_plot.R
#
# Density (top) + one horizontal box plot (middle) comparing:
#   • Combined propositions (per-paragraph similarity)
#   • Combined Triple-Sentences (paragraph-level similarity)
#   • STS-B reference bins 4–5 and 5 (in the same box panel)
# Also prints 1-Wasserstein distances to STS-B bin 5 and bin 4–5.
#
# install.packages(c("readr","dplyr","ggplot2","patchwork","scales","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(scales); library(knitr)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_comb <- "propositions_combined.csv"
csv_sing <- "single_extraction.csv"
csv_stsb <- "stsb_miniLM_cosines.csv"

out_png  <- "04_03_TRIPLE_VS_PROPOSITIONS_v2.png"
adjust_k <- 0.8  # KDE bandwidth

# ── load & tidy (combined + single) ───────────────────────────────────────
if (!file.exists(csv_comb)) stop("Missing file: ", csv_comb)
if (!file.exists(csv_sing)) stop("Missing file: ", csv_sing)
if (!file.exists(csv_stsb)) stop("Missing file: ", csv_stsb)

df_comb <- read_csv(csv_comb, show_col_types = FALSE)
df_sing <- read_csv(csv_sing, show_col_types = FALSE)
stsb_raw <- read_csv(csv_stsb, show_col_types = FALSE)

need1 <- c("paragraph_id","combined_proposition_similarity")
need2 <- c("paragraph_id","combined_similarity")
if (!all(need1 %in% names(df_comb))) stop("propositions_combined.csv must contain: ", paste(need1, collapse=", "))
if (!all(need2 %in% names(df_sing))) stop("single_extraction.csv must contain: ", paste(need2, collapse=", "))

df_long <- bind_rows(
  df_comb %>%
    transmute(metric = "Combined propositions",
              value  = as.numeric(combined_proposition_similarity)),
  df_sing %>%
    transmute(metric = "Combined Triple-Sentences",
              value  = as.numeric(combined_similarity))
) %>%
  filter(!is.na(value)) %>%
  mutate(value = pmin(pmax(value, 0), 1))

if (nrow(df_long) == 0) stop("No valid values to plot after cleaning.")

metric_levels <- c("Combined propositions", "Combined Triple-Sentences")
df_long$metric <- factor(df_long$metric, levels = metric_levels, ordered = TRUE)

# ── summary stats (for the two distributions) ─────────────────────────────
get_mode_kde <- function(v) { d <- density(v, from = 0, to = 1); d$x[which.max(d$y)] }

summary_df <- df_long %>%
  group_by(metric) %>%
  summarise(
    n      = n(),
    mean   = mean(value),
    median = median(value),
    q1     = quantile(value, 0.25),
    q3     = quantile(value, 0.75),
    sd     = sd(value),
    min    = min(value),
    max    = max(value),
    mode_kde = get_mode_kde(value),
    .groups = "drop"
  )

pretty_tbl <- summary_df %>%
  transmute(
    Series = as.character(metric),
    n,
    Min    = round(min, 3),
    Q1     = round(q1, 3),
    Median = round(median, 3),
    Mean   = round(mean, 3),
    Q3     = round(q3, 3),
    Max    = round(max, 3),
    SD     = round(sd, 3),
    Mode_KDE = round(mode_kde, 3)
  )

cat("\nSummary metrics: Combined propositions vs Combined Triple-Sentences\n\n")
kable(pretty_tbl, align = "lccccccccc")

dens_lines <- summary_df %>% transmute(metric = as.character(metric), mean, median)

# ── colours & linetypes for the two series ───────────────────────────────
fills <- c("Combined propositions"      = "#1f77b4",  # dark blue
           "Combined Triple-Sentences"  = "#d62728")  # dark red
metric_ltys <- c("Combined propositions"      = "solid",
                 "Combined Triple-Sentences"  = "22")  # short-dash

# ── density panel (two distributions) ─────────────────────────────────────
p_dens <- ggplot(df_long, aes(x = value)) +
  geom_density(aes(fill = metric, linetype = metric),
               colour    = "black",
               linewidth = 0.5,
               alpha     = 0.35,
               adjust    = adjust_k) +
  geom_vline(data = dens_lines,
             aes(xintercept = mean, colour = metric),
             linetype = "dashed", linewidth = 0.6, show.legend = FALSE) +
  geom_vline(data = dens_lines,
             aes(xintercept = median, colour = metric),
             linetype = "dotted", linewidth = 0.6, show.legend = FALSE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills, name = "Distribution") +
  scale_linetype_manual(values = metric_ltys, name = "Distribution") +
  scale_colour_manual(values = fills, guide = "none") +
  theme_bw(base_size = 11) +
  theme(
    panel.grid.minor = element_blank(),
    legend.position  = "top"
  )

# ── STS-B processing (keep only bins 4–5 and 5) ───────────────────────────
stsb_df <- stsb_raw %>%
  mutate(
    bin = case_when(
      gold_score == 5                       ~ "5",
      gold_score >= 4 & gold_score < 5      ~ "4–5",
      gold_score >= 3 & gold_score < 4      ~ "3–4",
      gold_score >= 2 & gold_score < 3      ~ "2–3",
      gold_score >= 1 & gold_score < 2      ~ "1–2",
      TRUE                                  ~ "0–1"
    ),
    bin = factor(bin, levels = c("0–1","1–2","2–3","3–4","4–5","5"), ordered = TRUE)
  )

stsb_sel <- stsb_df %>%
  filter(bin %in% c("4–5","5")) %>%
  mutate(metric = ifelse(bin == "5", "STS-B (5)", "STS-B (4–5)")) %>%
  transmute(metric, value = as.numeric(cosine)) %>%
  filter(!is.na(value)) %>%
  mutate(value = pmin(pmax(value, 0), 1))

# summary for STS-B (for box v-lines & colours)
stsb_summary_df <- stsb_sel %>%
  group_by(metric) %>%
  summarise(
    n      = n(),
    mean   = mean(value),
    median = median(value),
    q1     = quantile(value, 0.25),
    q3     = quantile(value, 0.75),
    sd     = sd(value),
    min    = min(value),
    max    = max(value),
    mode_kde = get_mode_kde(value),
    .groups = "drop"
  )

# pastel ramp keyed to each STS-B bin’s median (Red→Amber→Mint)
anchor_cols <- c("#fbb4ae", "#fff2ae", "#b3e2cd")
grad_fun    <- colorRampPalette(anchor_cols)
cols_cont   <- grad_fun(1000)
col_for_val <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]
stsb_cols <- c(
  "STS-B (4–5)" = col_for_val(stsb_summary_df$median[stsb_summary_df$metric == "STS-B (4–5)"]),
  "STS-B (5)"   = col_for_val(stsb_summary_df$median[stsb_summary_df$metric == "STS-B (5)"])
)

# ── combine for the SINGLE box panel (series + STS-B rows) ────────────────
df_box_long <- bind_rows(
  df_long,
  stsb_sel
)

summary_df_box <- bind_rows(
  summary_df,
  stsb_summary_df
)

# order: two series first, then STS-B rows beneath
box_levels <- c("Combined propositions", "Combined Triple-Sentences",
                "STS-B (5)", "STS-B (4–5)")
df_box_long$metric     <- factor(df_box_long$metric, levels = box_levels, ordered = TRUE)
summary_df_box$metric  <- factor(summary_df_box$metric, levels = box_levels, ordered = TRUE)

# unified fill palette for the box panel
box_fills <- c(fills, stsb_cols)

# ── single horizontal box & whiskers ──────────────────────────────────────
p_box <- ggplot(df_box_long, aes(x = value, y = metric, fill = metric)) +
  geom_boxplot(colour = "black",
               width = 0.18,
               outlier.shape = 16, outlier.size = 0.9,
               linewidth = 0.35) +
  geom_vline(data = summary_df_box,
             aes(xintercept = mean, colour = metric),
             linetype = "dashed", linewidth = 0.5, show.legend = FALSE) +
  geom_vline(data = summary_df_box,
             aes(xintercept = median, colour = metric),
             linetype = "dotted", linewidth = 0.5, show.legend = FALSE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0),
                     name = "Cosine similarity (0–1)") +
  scale_y_discrete(limits = rev(box_levels), labels = NULL) +
  scale_fill_manual(values = box_fills, guide = "none") +
  scale_colour_manual(values = box_fills, guide = "none") +
  labs(subtitle = "Box & Whiskers: Propositions (blue) • Triple-Sentences (red) • STS-B bins 4 & 5 (green)") +
  theme_bw(base_size = 11) +
  theme(
    plot.subtitle    = element_text(hjust = 0.5),
    panel.grid.minor = element_blank(),
    axis.ticks.y     = element_blank()
  )

# ── 1-Wasserstein distance (Earth Mover’s Distance in 1D) ─────────────────
# W1(F,G) = ∫_0^1 |F^{-1}(t) − G^{-1}(t)| dt, approximated via quantiles
w1_quantile <- function(x, y, m = 1000) {
  x <- x[is.finite(x)]; y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(NA_real_)
  probs <- seq(0, 1, length.out = m)
  qx <- quantile(x, probs = probs, type = 7, names = FALSE)
  qy <- quantile(y, probs = probs, type = 7, names = FALSE)
  mean(abs(qx - qy))
}

# reference distributions
ref_bin5  <- stsb_sel %>% filter(metric == "STS-B (5)")   %>% pull(value)
ref_bin45 <- stsb_sel %>% filter(metric == "STS-B (4–5)") %>% pull(value)

prop_vals <- df_long %>% filter(metric == "Combined propositions")     %>% pull(value)
trip_vals <- df_long %>% filter(metric == "Combined Triple-Sentences") %>% pull(value)

w1_tbl <- tibble::tibble(
  Comparison = c("Propositions", "Triple-Sentences"),
  W1_to_STSB_5    = c(w1_quantile(prop_vals, ref_bin5),
                      w1_quantile(trip_vals, ref_bin5)),
  W1_to_STSB_4_5  = c(w1_quantile(prop_vals, ref_bin45),
                      w1_quantile(trip_vals, ref_bin45))
) %>%
  mutate(across(starts_with("W1_"), ~round(.x, 4)))

cat("\n1-Wasserstein distance to STS-B bins (smaller = closer; range 0–1)\n\n")
kable(w1_tbl, align = "lcc")

# ── assemble & save (two panels) ──────────────────────────────────────────
combined_plot <- p_dens / p_box +
  plot_layout(heights = c(3.0, 1.4))

ggsave(
  filename = out_png,
  plot     = combined_plot,
  width    = 200,  # mm
  height   = 180,  # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved figure to: ", out_png)