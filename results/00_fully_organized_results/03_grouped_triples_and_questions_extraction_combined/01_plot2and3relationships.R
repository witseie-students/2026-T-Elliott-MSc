# 01_plot2and3relationships.R
#
# One figure with:
#   0) Legend row (separate grob)  ← placed ABOVE the first density plot title
#   1) Density overlay (Triples=blue, Q&A=red): "2 relationships extracted"
#   2) Density overlay (Triples=blue, Q&A=red): "3 or more relationships extracted"
#   3) Combined horizontal box & whiskers:
#        - Triples (2 rels), Q&A (2 rels)
#        - Triples (3+ rels), Q&A (3+ rels)
#        - STS-B bins 3–4, 4–5, 5 (R–A–G by each bin's median)
#
# Inputs (in this folder):
#   - combined_from_triple_similarities.csv  OR  combined_from_triples_similarities2.csv
#       (paragraph_id, proposition_id, n_triples,
#        triple_combined_similarity, qa_combined_similarity)
#   - stsb_miniLM_cosines.csv  (gold_score, cosine)
#
# Output:
#   - 01_relationships_2_and_3plus.png
#
# install.packages(c("readr","dplyr","ggplot2","patchwork","cowplot","knitr"))

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
  library(patchwork); library(cowplot); library(knitr)
})

# ── files (support singular/plural name) ──────────────────────────────────
csv_try1 <- "combined_from_triple_similarities.csv"    # singular
csv_try2 <- "combined_from_triples_similarities2.csv"  # plural
csv_main <- if (file.exists(csv_try1)) csv_try1 else csv_try2
csv_stsb <- "stsb_miniLM_cosines.csv"
out_png  <- "04_05_2&3relationshipsextractedcombined_v2.png"

stopifnot(file.exists(csv_main), file.exists(csv_stsb))

# ── load & tidy main data ─────────────────────────────────────────────────
need_cols <- c("paragraph_id","proposition_id","n_triples",
               "triple_combined_similarity","qa_combined_similarity")

df_all <- read_csv(csv_main, show_col_types = FALSE)
if (!all(need_cols %in% names(df_all))) {
  stop(basename(csv_main), " must contain: ", paste(need_cols, collapse=", "))
}

df_all <- df_all %>%
  mutate(
    n_triples = as.integer(n_triples),
    triple_combined_similarity = pmin(pmax(as.numeric(triple_combined_similarity), 0), 1),
    qa_combined_similarity     = pmin(pmax(as.numeric(qa_combined_similarity), 0), 1)
  )

# groups
df2  <- df_all %>% filter(n_triples == 2)
df3p <- df_all %>% filter(n_triples >= 3)

tri_g2 <- df2  %>% filter(!is.na(triple_combined_similarity)) %>% pull(triple_combined_similarity)
ans_g2 <- df2  %>% filter(!is.na(qa_combined_similarity))     %>% pull(qa_combined_similarity)
tri_g3 <- df3p %>% filter(!is.na(triple_combined_similarity)) %>% pull(triple_combined_similarity)
ans_g3 <- df3p %>% filter(!is.na(qa_combined_similarity))     %>% pull(qa_combined_similarity)

if ((length(tri_g2)==0 & length(ans_g2)==0) &&
    (length(tri_g3)==0 & length(ans_g3)==0)) {
  stop("No valid similarity values in either group (n_triples==2, n_triples>=3).")
}

# ── STS-B bins (ONLY 3–4, 4–5, 5) with R–A–G by bin median ───────────────
stsb <- read_csv(csv_stsb, show_col_types = FALSE) %>%
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
  filter(bin %in% c("3–4","4–5","5")) %>%   # ← removed "2–3"
  transmute(series = paste0("STS ", bin), value)

# R–A–G palette
pastel_red   <- "#fbb4ae"
pastel_amber <- "#fff2ae"
pastel_mint  <- "#b3e2cd"
grad_fun     <- colorRampPalette(c(pastel_red, pastel_amber, pastel_mint))
cols_cont    <- grad_fun(1000)
col_for_val  <- function(x) cols_cont[pmax(1, pmin(1000, round(x * 999) + 1))]

stsb_meds <- stsb %>% group_by(series) %>% summarise(median = median(value), .groups = "drop")
stsb_cols <- setNames(col_for_val(stsb_meds$median), stsb_meds$series)

# ── colours & legend order ────────────────────────────────────────────────
col_tri <- "#1f77b4"  # blue
col_ans <- "#d62728"  # red

legend_order <- c("Triple back-validation", "Question-Answer back-validation")
fills_density <- c("Triple back-validation" = col_tri,
                   "Question-Answer back-validation" = col_ans)
ltys_density  <- c("Triple back-validation" = "solid",
                   "Question-Answer back-validation" = "22")  # short-dash

# ── helper (console summaries) ────────────────────────────────────────────
get_mode_kde <- function(v) {
  if (length(v) < 2) return(NA_real_)
  d <- density(v, from = 0, to = 1)
  d$x[which.max(d$y)]
}
print_stats <- function(vals_tri, vals_ans, title) {
  if (length(vals_tri)==0 & length(vals_ans)==0) return(invisible(NULL))
  summ <- tibble(
    series   = c("Triple back-validation", "Answer back-validation"),
    n        = c(length(vals_tri), length(vals_ans)),
    mean     = c(mean(vals_tri),  mean(vals_ans)),
    median   = c(median(vals_tri), median(vals_ans)),
    q1       = c(quantile(vals_tri, 0.25), quantile(vals_ans, 0.25)),
    q3       = c(quantile(vals_tri, 0.75), quantile(vals_ans, 0.75)),
    sd       = c(sd(vals_tri), sd(vals_ans)),
    min      = c(min(vals_tri), min(vals_ans)),
    max      = c(max(vals_tri), max(vals_ans)),
    mode_kde = c(get_mode_kde(vals_tri), get_mode_kde(vals_ans))
  )
  cat("\n", title, "\n", sep = "")
  print(knitr::kable(summ %>% mutate(across(where(is.numeric), ~ round(.x, 4))),
                     align = "lccccccccc"))
}
print_stats(tri_g2, ans_g2, "Summary metrics — 2 relationships extracted")
print_stats(tri_g3, ans_g3, "Summary metrics — 3 or more relationships extracted")

# ── density overlay builder (Triples+Answers together) ────────────────────
make_overlay <- function(vals_tri, vals_ans, title_txt, show_legend = TRUE) {
  df_dens <- bind_rows(
    tibble(series = "Triple back-validation",  value = vals_tri),
    tibble(series = "Question-Answer back-validation",  value = vals_ans)
  ) %>% filter(!is.na(value)) %>%
    mutate(series = factor(series, levels = legend_order, ordered = TRUE))

  summ <- tibble(
    series = factor(legend_order, levels = legend_order, ordered = TRUE),
    mean   = c(ifelse(length(vals_tri)>0, mean(vals_tri), NA_real_),
               ifelse(length(vals_ans)>0,  mean(vals_ans),  NA_real_)),
    median = c(ifelse(length(vals_tri)>0, median(vals_tri), NA_real_),
               ifelse(length(vals_ans)>0,  median(vals_ans),  NA_real_))
  )

  ggplot(df_dens, aes(x = value)) +
    geom_density(aes(fill = series, linetype = series),
                 colour = "black", linewidth = 0.5, alpha = 0.35, adjust = 0.8, na.rm = TRUE) +
    geom_vline(data = summ, aes(xintercept = mean, colour = series),
               linetype = "dashed", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
    geom_vline(data = summ, aes(xintercept = median, colour = series),
               linetype = "dotted", linewidth = 0.6, show.legend = FALSE, na.rm = TRUE) +
    scale_x_continuous(limits = c(0,1), expand = c(0,0), name = NULL) +
    scale_y_continuous(expand = c(0,0), name = "Density") +
    scale_fill_manual(values = fills_density, breaks = legend_order, name = NULL) +
    scale_linetype_manual(values = ltys_density, breaks = legend_order, name = NULL) +
    scale_colour_manual(values = fills_density, guide = "none") +
    labs(title = title_txt) +
    theme_bw(base_size = 11) +
    theme(panel.grid.minor = element_blank(),
          legend.position  = if (show_legend) "top" else "none",
          plot.title       = element_text(hjust = 0.5))
}

# Build first density WITH legend (to extract it)
p_dens_g2_full <- make_overlay(tri_g2, ans_g2, "2 relationships extracted", show_legend = TRUE)

# Extract legend as its own grob (single row), place ABOVE the title
legend_g <- cowplot::get_legend(
  p_dens_g2_full +
    guides(fill = guide_legend(nrow = 1), linetype = guide_legend(nrow = 1)) +
    theme(legend.position = "top", legend.box = "horizontal")
)

# Now rebuild the first density WITHOUT legend (title stays)
p_dens_g2 <- p_dens_g2_full + theme(legend.position = "none")

# Second density (no legend)
p_dens_g3 <- make_overlay(tri_g3, ans_g3, "3 or more relationships extracted", show_legend = FALSE)

# ── combined box & whiskers (2 rels, 3+ rels, STS bins 3–4/4–5/5) ────────
df_box <- bind_rows(
  tibble(series = "Triples (2 rels)",  value = tri_g2),
  tibble(series = "Q&A (2 rels)",      value = ans_g2),
  tibble(series = "Triples (3+ rels)", value = tri_g3),
  tibble(series = "Q&A (3+ rels)",     value = ans_g3),
  stsb
) %>% filter(!is.na(value))

# Vertical order (top → bottom): 2-rels, 3+-rels, then STS bins (no 2–3)
y_levels <- c("Triples (2 rels)", "Q&A (2 rels)",
              "Triples (3+ rels)", "Q&A (3+ rels)",
              "STS 5", "STS 4–5", "STS 3–4")
df_box$series <- factor(df_box$series, levels = y_levels, ordered = TRUE)

# Fill mapping (blue for Triples, red for Q&A, R–A–G for STS)
fills_all <- c(
  "Triples (2 rels)"  = col_tri,
  "Q&A (2 rels)"      = col_ans,
  "Triples (3+ rels)" = col_tri,
  "Q&A (3+ rels)"     = col_ans,
  stsb_cols
)

p_box <- ggplot(df_box, aes(x = value, y = series, fill = series)) +
  geom_boxplot(colour = "black",
               width = 0.18, outlier.shape = 16, outlier.size = 0.9, linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), expand = c(0,0),
                     name = "Cosine similarity (0–1)") +
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
  height   = 235,  # mm
  units    = "mm",
  dpi      = 900,
  bg       = "white"
)

message("Saved figure to: ", out_png)