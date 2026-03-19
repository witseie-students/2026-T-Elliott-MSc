# 01_plot_single_relationship.R
#
# Single-relationship (n_relationships == 1) plots:
#   • Top: density overlay — Triple (blue) then Q&A (red) in the legend
#   • Bottom: one combined horizontal box & whiskers that includes:
#       - Triple (blue)  [TOP]
#       - Q&A (red)
#       - STS-B bins: 3–4, 4–5, 5          [BOTTOM]
#
# Inputs (in this folder):
#   - group_1_relationship.csv    (paragraph_id, proposition_id, quad_index, triple_similarity, qa_similarity[, n_relationships])
#   - stsb_miniLM_cosines.csv     (gold_score, cosine)
#
# Output:
#   - 01_relationship.png
#
# install.packages(c("readr","dplyr","ggplot2","patchwork"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2); library(patchwork)
})

csv_g1  <- "group_1_relationship.csv"
csv_sts <- "stsb_miniLM_cosines_no_bin5.csv"
out_png <- "04_05_1relationship_v2.png"

stopifnot(file.exists(csv_g1), file.exists(csv_sts))

# ── load single-relationship data ─────────────────────────────────────────
df1 <- read_csv(csv_g1, show_col_types = FALSE)

need_cols <- c("paragraph_id","proposition_id","quad_index","triple_similarity","qa_similarity")
if (!all(need_cols %in% names(df1))) {
  stop("group_1_relationship.csv must contain: ", paste(need_cols, collapse=", "))
}

# if n_relationships exists, keep == 1 (but group_1 file should be single already)
if ("n_relationships" %in% names(df1)) {
  df1 <- df1 %>% filter(n_relationships == 1)
}

df1 <- df1 %>%
  mutate(
    triple_similarity = pmin(pmax(as.numeric(triple_similarity), 0), 1),
    qa_similarity     = pmin(pmax(as.numeric(qa_similarity), 0), 1)
  )

tri_vals <- df1 %>% filter(!is.na(triple_similarity)) %>% pull(triple_similarity)
qa_vals  <- df1 %>% filter(!is.na(qa_similarity))     %>% pull(qa_similarity)

if (length(tri_vals) == 0 & length(qa_vals) == 0) {
  stop("No valid similarity values found in group_1_relationship.csv")
}

# ── summary lines for densities ───────────────────────────────────────────
summ_density <- tibble(
  series = c("Triple back-validation", "Question-Answer back-validation"),
  mean   = c(ifelse(length(tri_vals)>0, mean(tri_vals), NA_real_),
             ifelse(length(qa_vals)>0,  mean(qa_vals),  NA_real_)),
  median = c(ifelse(length(tri_vals)>0, median(tri_vals), NA_real_),
             ifelse(length(qa_vals)>0,  median(qa_vals),  NA_real_))
)

# ── colors (triple blue, Q&A red) ─────────────────────────────────────────
col_tri <- "#1f77b4"  # dark blue
col_qa  <- "#d62728"  # dark red

fills_density <- c("Triple back-validation" = col_tri,
                   "Question-Answer back-validation"    = col_qa)

ltys_density  <- c("Triple back-validation" = "solid",
                   "Question-Answer back-validation"    = "22")  # short-dash

# Desired legend order
legend_order <- c("Triple back-validation", "Question-Answer back-validation")

# ── density overlay data ──────────────────────────────────────────────────
df_dens <- bind_rows(
  tibble(series = "Triple back-validation", value = tri_vals),
  tibble(series = "Question-Answer back-validation",    value = qa_vals)
) %>%
  mutate(series = factor(series, levels = legend_order, ordered = TRUE))

# Ensure the summary table uses same factor order (for colored vlines)
summ_density$series <- factor(summ_density$series, levels = legend_order, ordered = TRUE)

# ── density panel ─────────────────────────────────────────────────────────
p_dens <- ggplot(df_dens, aes(x = value)) +
  geom_density(aes(fill = series, linetype = series),
               colour = "black", linewidth = 0.5, alpha = 0.35, adjust = 0.8) +
  geom_vline(data = summ_density, aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  geom_vline(data = summ_density, aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills_density, breaks = legend_order, name = NULL) +
  scale_linetype_manual(values = ltys_density, breaks = legend_order, name = NULL) +
  scale_colour_manual(values = fills_density, guide = "none") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        legend.position  = "top")

# ── STS-B: load & prepare bins 3–4, 4–5, 5 ───────────────────────────────
stsb <- read_csv(csv_sts, show_col_types = FALSE) %>%
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

# R–A–G palette for STS bins (by each bin's median)
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
grad_fun     <- colorRampPalette(c(pastel_red, pastel_amber, pastel_mint))
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_meds <- stsb_bins %>%
  group_by(series) %>%
  summarise(median = median(value), .groups = "drop")

stsb_cols <- setNames(col_for_val(stsb_meds$median), stsb_meds$series)

# ── combined box data (Triple, Q&A, and STS bins) ─────────────────────────
df_box <- bind_rows(
  tibble(series = "Triple back-validation", value = tri_vals),
  tibble(series = "Question-Answer back-validation",    value = qa_vals),
  stsb_bins
) %>% filter(!is.na(value))

# Desired vertical order (top → bottom):
#   Triple (blue), Q&A (red), then STS bins (5, 4–5, 3–4)
y_levels <- c("Triple back-validation",
              "Question-Answer back-validation",
              "STS 5", "STS 4–5", "STS 3–4")

df_box$series <- factor(df_box$series, levels = y_levels, ordered = TRUE)

# Fill map for all series
fills_all <- c(
  "Triple back-validation" = col_tri,
  "Question-Answer back-validation"    = col_qa,
  stsb_cols
)

# ── combined horizontal box & whiskers ────────────────────────────────────
p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18, outlier.shape = 16, outlier.size = 0.9, linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = "Cosine similarity (0–1)") +
  # Triple & Q&A ABOVE the STS bins:
  scale_y_discrete(limits = rev(y_levels), labels = NULL) +
  scale_fill_manual(values = fills_all, guide = "none") +
  labs(subtitle = "Box & whiskers: Triple-sentence (blue), Question-Answer (red), and STS-B bins 3, 4 & 5 (green)") +
  theme_bw(base_size = 11) +
  theme(plot.subtitle    = element_text(hjust = 0.5),
        panel.grid.minor = element_blank(),
        axis.ticks.y     = element_blank())

# ── assemble & save ───────────────────────────────────────────────────────
final_plot <- p_dens / p_box +
  plot_layout(heights = c(2.6, 1.3))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = 200,  # mm
  height   = 160,  # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved figure to: ", out_png)