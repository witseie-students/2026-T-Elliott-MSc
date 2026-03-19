# 02_plot_two_and_threeplus_relationships.R
#
# Panels (top → bottom):
#   0) Legend row (separate grob)  ← placed ABOVE the first plot title
#   1) Density overlay for "2 relationships extracted"
#   2) Density overlay for "3 or more relationships extracted"
#   3) One combined horizontal box & whiskers including:
#        - Triple (2 rels)   [blue]
#        - Q&A   (2 rels)    [red]
#        - Triple (3+ rels)  [blue]
#        - Q&A   (3+ rels)   [red]
#        - STS-B bins 2–3, 3–4, 4–5, 5 (R–A–G by each bin's median)
#
# Inputs (in this folder):
#   - group_2_relationships.csv
#   - group_3plus_relationships.csv
#   - stsb_miniLM_cosines.csv
#
# Output:
#   - 02_relationships_2_and_3plus.png
#
# install.packages(c("readr","dplyr","ggplot2","patchwork","cowplot"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(cowplot)
})

# ── files ─────────────────────────────────────────────────────────────────
csv_g2  <- "group_2_relationships.csv"
csv_g3p <- "group_3plus_relationships.csv"
csv_sts <- "stsb_miniLM_cosines_no_bin5.csv"
out_png <- "04_05_2and3plus_relationships_v2.png"

stopifnot(file.exists(csv_g2), file.exists(csv_g3p), file.exists(csv_sts))

# ── load helper ───────────────────────────────────────────────────────────
.read_group <- function(path, expect_note) {
  need <- c("paragraph_id","proposition_id","quad_index","triple_similarity","qa_similarity")
  df <- read_csv(path, show_col_types = FALSE)
  if (!all(need %in% names(df))) {
    stop(expect_note, " must contain: ", paste(need, collapse=", "))
  }
  df %>%
    mutate(
      triple_similarity = pmin(pmax(as.numeric(triple_similarity), 0), 1),
      qa_similarity     = pmin(pmax(as.numeric(qa_similarity), 0), 1)
    )
}

g2  <- .read_group(csv_g2,  "group_2_relationships.csv")
g3p <- .read_group(csv_g3p, "group_3plus_relationships.csv")

tri_g2 <- g2  %>% filter(!is.na(triple_similarity)) %>% pull(triple_similarity)
qa_g2  <- g2  %>% filter(!is.na(qa_similarity))     %>% pull(qa_similarity)
tri_g3 <- g3p %>% filter(!is.na(triple_similarity)) %>% pull(triple_similarity)
qa_g3  <- g3p %>% filter(!is.na(qa_similarity))     %>% pull(qa_similarity)

if ((length(tri_g2)==0 & length(qa_g2)==0) &&
    (length(tri_g3)==0 & length(qa_g3)==0)) {
  stop("No valid similarity values found in both groups.")
}

# ── styles (triple blue, Q&A red) & legend order ──────────────────────────
col_tri <- "#1f77b4"  # dark blue
col_qa  <- "#d62728"  # dark red

legend_order <- c("Triple back-validation", "Question-Answer back-validation")
fills_density <- c("Triple back-validation" = col_tri,
                   "Question-Answer back-validation" = col_qa)
ltys_density  <- c("Triple back-validation" = "solid",
                   "Question-Answer back-validation" = "22")  # short-dash

# ── density for "2 relationships extracted" (will carry the legend) ──────
df_dens_g2 <- bind_rows(
  tibble(series = "Triple back-validation",            value = tri_g2),
  tibble(series = "Question-Answer back-validation",   value = qa_g2)
) %>% mutate(series = factor(series, levels = legend_order, ordered = TRUE))

summ_g2 <- tibble(
  series = factor(legend_order, levels = legend_order, ordered = TRUE),
  mean   = c(ifelse(length(tri_g2)>0, mean(tri_g2), NA_real_),
             ifelse(length(qa_g2)>0,  mean(qa_g2),  NA_real_)),
  median = c(ifelse(length(tri_g2)>0, median(tri_g2), NA_real_),
             ifelse(length(qa_g2)>0,  median(qa_g2),  NA_real_))
)

p_dens_g2 <- ggplot(df_dens_g2, aes(x = value)) +
  geom_density(aes(fill = series, linetype = series),
               colour = "black", linewidth = 0.5, alpha = 0.35, adjust = 0.8, na.rm = TRUE) +
  geom_vline(data = summ_g2, aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  geom_vline(data = summ_g2, aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills_density, breaks = legend_order, name = NULL) +
  scale_linetype_manual(values = ltys_density, breaks = legend_order, name = NULL) +
  scale_colour_manual(values = fills_density, guide = "none") +
  labs(title = "2 relationships extracted") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        legend.position  = "top",      # we will extract this legend
        plot.title       = element_text(hjust = 0.5))

# ── EXTRACT legend as its own grob (so we can place it above the title) ──
legend_g <- cowplot::get_legend(
  p_dens_g2 +
    guides(fill = guide_legend(nrow = 1), linetype = guide_legend(nrow = 1)) +
    theme(legend.position = "top",
          legend.box      = "horizontal")
)

# Now remove legends from the actual plots
p_dens_g2 <- p_dens_g2 + theme(legend.position = "none")

# ── density for "3 or more relationships extracted" (no legend) ──────────
df_dens_g3 <- bind_rows(
  tibble(series = "Triple back-validation",            value = tri_g3),
  tibble(series = "Question-Answer back-validation",   value = qa_g3)
) %>% mutate(series = factor(series, levels = legend_order, ordered = TRUE))

summ_g3 <- tibble(
  series = factor(legend_order, levels = legend_order, ordered = TRUE),
  mean   = c(ifelse(length(tri_g3)>0, mean(tri_g3), NA_real_),
             ifelse(length(qa_g3)>0,  mean(qa_g3),  NA_real_)),
  median = c(ifelse(length(tri_g3)>0, median(tri_g3), NA_real_),
             ifelse(length(qa_g3)>0,  median(qa_g3),  NA_real_))
)

p_dens_g3 <- ggplot(df_dens_g3, aes(x = value)) +
  geom_density(aes(fill = series, linetype = series),
               colour = "black", linewidth = 0.5, alpha = 0.35, adjust = 0.8, na.rm = TRUE) +
  geom_vline(data = summ_g3, aes(xintercept = mean, colour = series),
             linetype = "dashed", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  geom_vline(data = summ_g3, aes(xintercept = median, colour = series),
             linetype = "dotted", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
  scale_y_continuous(expand = c(0,0), name = "Density") +
  scale_fill_manual(values = fills_density, breaks = legend_order, name = NULL) +
  scale_linetype_manual(values = ltys_density, breaks = legend_order, name = NULL) +
  scale_colour_manual(values = fills_density, guide = "none") +
  labs(title = "3 or more relationships extracted") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        legend.position  = "none",
        plot.title       = element_text(hjust = 0.5))

# ── STS-B: bins 2–3, 3–4, 4–5, 5 (R–A–G by bin median) ───────────────────
stsb <- read_csv(csv_sts, show_col_types = FALSE) %>%
  filter(!is.na(gold_score), !is.na(cosine)) %>%
  mutate(
    value = pmin(pmax(as.numeric(cosine), 0), 1),
    bin = case_when(
      gold_score == 5                  ~ "5",
      gold_score >= 4 & gold_score < 5 ~ "4–5",
      gold_score >= 3 & gold_score < 4 ~ "3–4",
      gold_score >= 2 & gold_score < 3 ~ "2–3",
      gold_score >= 1 & gold_score < 2 ~ "1–2",
      TRUE                             ~ "0–1"
    )
  ) %>%
  filter(bin %in% c("2–3","3–4","4–5","5")) %>%
  transmute(series = paste0("STS ", bin), value)

# R–A–G mapping by each bin's median
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
grad_fun     <- colorRampPalette(c(pastel_red, pastel_amber, pastel_mint))
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_meds <- stsb %>% group_by(series) %>% summarise(median = median(value), .groups = "drop")
stsb_cols <- setNames(col_for_val(stsb_meds$median), stsb_meds$series)

# ── combined box data (2 rels, 3+ rels, STS bins) ────────────────────────
df_box <- bind_rows(
  tibble(series = "Triple (2 rels)",  value = tri_g2),
  tibble(series = "Q&A (2 rels)",     value = qa_g2),
  tibble(series = "Triple (3+ rels)", value = tri_g3),
  tibble(series = "Q&A (3+ rels)",    value = qa_g3),
  stsb
) %>% filter(!is.na(value))

# Vertical order (top → bottom): 2-rels, 3+-rels, then STS bins
y_levels <- c("Triple (2 rels)", "Q&A (2 rels)",
              "Triple (3+ rels)", "Q&A (3+ rels)",
              "STS 5", "STS 4–5", "STS 3–4", "STS 2–3")
df_box$series <- factor(df_box$series, levels = y_levels, ordered = TRUE)

# Fill mapping (blue for Triples, red for Q&A, R–A–G for STS)
fills_all <- c(
  "Triple (2 rels)"  = col_tri,
  "Q&A (2 rels)"     = col_qa,
  "Triple (3+ rels)" = col_tri,
  "Q&A (3+ rels)"    = col_qa,
  stsb_cols
)

# ── single combined horizontal box & whiskers ────────────────────────────
p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18, outlier.shape = 16, outlier.size = 0.9, linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0), name = "Cosine similarity (0–1)") +
  scale_y_discrete(limits = rev(y_levels), labels = NULL) +
  scale_fill_manual(values = fills_all, guide = "none") +
  labs(subtitle = "Box & whiskers: Triple-sentence (blue), Question-Answer (red), and STS-B bins 3, 4 & 5 (green)") +
  theme_bw(base_size = 11) +
  theme(plot.subtitle    = element_text(hjust = 0.5),
        panel.grid.minor = element_blank(),
        axis.ticks.y     = element_blank())

# ── assemble with legend row ABOVE the first plot title ───────────────────
legend_row <- patchwork::wrap_elements(full = legend_g)

final_plot <- (legend_row / p_dens_g2 / p_dens_g3 / p_box) +
  plot_layout(heights = c(0.5, 2.2, 2.2, 2.2))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = 200,  # mm
  height   = 240,  # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved figure to: ", out_png)