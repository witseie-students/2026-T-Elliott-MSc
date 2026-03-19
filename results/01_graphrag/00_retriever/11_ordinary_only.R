# 11_ordinary_only.R
# ════════════════════════════════════════════════════════════════════════════
# “Ordinary-only” vs “Inferred-only” vs “Rank-1 (all)” similarity analysis
#
# PANELS  (top → bottom)
# ─────────────────────────────────────────────────────────────────────────────
# A. Density overlay  : Top-ordinary  **and**  Top-inferred
# B. Density (single) : Rank-1 neighbours (all)
# C. Box & whiskers   : Three groups
#        – Top-ordinary
#        – Top-inferred
#        – Rank-1 (all)
#
#  • Top-ordinary  = highest-rank neighbour whose relationship is *not* inferred
#  • Top-inferred  = highest-rank neighbour whose relationship *is* inferred
#  • Rank-1 (all)  = whatever appears at Rank 1 (could be inferred or not)
#
#  • Y-axis on density plots is fixed at 0 – 7 for comparability.
#  • Console prints coverage stats for each group (out of the expected
#    350 abstracts).
#
#  • Input  : 09_question_cosines_inferred.csv   (same directory)
#  • Output : 11_ordinary_only.png              (same directory)
# ════════════════════════════════════════════════════════════════════════════

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2);  library(patchwork)
})

# ─────────────────────────────────────────────────────────────────────────────
#  I/O
# ─────────────────────────────────────────────────────────────────────────────
csv_file <- "09_question_cosines_inferred.csv"
out_png  <- "11_ordinary_only.png"
if (!file.exists(csv_file))
  stop("Missing file: ", csv_file, call. = FALSE)

# ─────────────────────────────────────────────────────────────────────────────
#  FIGURE GEOMETRY
# ─────────────────────────────────────────────────────────────────────────────
FIG_W_MM  <- 180
DENS1_H_MM <-  70
DENS2_H_MM <-  70
BOX_H_MM   <-  50
DPI        <- 300

Y_MAX    <- 7
adjust_k <- 0.4

# ─────────────────────────────────────────────────────────────────────────────
#  LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
raw <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    inferred_flag     = tolower(trimws(inferred)) == "true"
  ) %>%
  filter(rank <= 20, !is.na(cosine_similarity))      # rank cap = safety

if (nrow(raw) == 0)
  stop("No rows after basic filtering.", call. = FALSE)

# ─────────────────────────────────────────────────────────────────────────────
#  BUILD THREE DATA SETS
# ─────────────────────────────────────────────────────────────────────────────
# 1. top ordinary (first non-inferred row per pubid)
df_topOrd <- raw %>%
  arrange(pubid, rank) %>%
  group_by(pubid) %>%
  filter(!inferred_flag) %>%
  slice_head(n = 1) %>%
  ungroup() %>%
  mutate(set = "Top-ordinary")

# 2. top inferred (first inferred row per pubid)
df_topInf <- raw %>%
  arrange(pubid, rank) %>%
  group_by(pubid) %>%
  filter(inferred_flag) %>%
  slice_head(n = 1) %>%
  ungroup() %>%
  mutate(set = "Top-inferred")

# 3. rank-1 (all)
df_rank1  <- raw %>%
  filter(rank == 1) %>%
  mutate(set = "Rank-1 (all)")

# ─────────────────────────────────────────────────────────────────────────────
#  COVERAGE REPORT
# ─────────────────────────────────────────────────────────────────────────────
TOTAL_ABS <- 350
cov_tbl <- tibble(
  set   = c("Top-ordinary", "Top-inferred", "Rank-1 (all)"),
  count = c(n_distinct(df_topOrd$pubid),
            n_distinct(df_topInf$pubid),
            n_distinct(df_rank1 $pubid))
) %>%
  mutate(pct = 100 * count / TOTAL_ABS)

message("Coverage out of 350 abstracts")
writeLines(sprintf("• %-14s : %3d (%.1f %%)",
                   cov_tbl$set, cov_tbl$count, cov_tbl$pct))

# ─────────────────────────────────────────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────────────────────────────────────────
COL_TOP_ORD <- "#1f77b4"   # blue
COL_TOP_INF <- "#2ca02c"   # green
COL_R1_ALL  <- "#d62728"   # red

# ── Density overlay (Top-ordinary & Top-inferred) ---------------------------
df_dens1 <- bind_rows(df_topOrd, df_topInf)

p_dens1 <- ggplot(df_dens1, aes(x = cosine_similarity, fill = set, colour = set)) +
  geom_density(alpha = 0.35,
               adjust = adjust_k, linewidth = 0.6) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0)) +
  scale_y_continuous(limits = c(0, Y_MAX), expand = c(0,0)) +
  scale_fill_manual(values = c("Top-ordinary" = COL_TOP_ORD,
                               "Top-inferred" = COL_TOP_INF),
                    name = NULL) +
  scale_colour_manual(values = c("Top-ordinary" = COL_TOP_ORD,
                                 "Top-inferred" = COL_TOP_INF),
                      name = NULL) +
  labs(title = "Top-ordinary vs Top-inferred",
       x = NULL, y = "Density") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "top")

# ── Density of Rank-1 (all) --------------------------------------------------
p_dens2 <- ggplot(df_rank1, aes(x = cosine_similarity)) +
  geom_density(fill = COL_R1_ALL, colour = "black", alpha = 0.35,
               adjust = adjust_k, linewidth = 0.4) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0)) +
  scale_y_continuous(limits = c(0, Y_MAX), expand = c(0,0)) +
  labs(title = "Rank-1 similarity distribution (all)",
       x = NULL, y = "Density") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank())

# ── Box-plot with three groups ----------------------------------------------
df_boxes <- bind_rows(df_topOrd, df_topInf, df_rank1)

p_box <- ggplot(df_boxes, aes(x = cosine_similarity, y = set, fill = set)) +
  geom_boxplot(colour = "black",
               width  = 0.6,
               outlier.shape = 16, outlier.size = 1.1,
               linewidth = 0.4) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0),
                     name   = "Cosine similarity (0 – 1)") +
  scale_y_discrete(NULL) +
  scale_fill_manual(values = c("Top-ordinary" = COL_TOP_ORD,
                               "Top-inferred" = COL_TOP_INF,
                               "Rank-1 (all)" = COL_R1_ALL),
                    guide = "none") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank())

# ─────────────────────────────────────────────────────────────────────────────
#  ASSEMBLE  &  SAVE
# ─────────────────────────────────────────────────────────────────────────────
final <- p_dens1 / p_dens2 / p_box +
  plot_layout(heights = c(DENS1_H_MM, DENS2_H_MM, BOX_H_MM)) &
  theme(plot.margin = margin(4,4,4,4,"mm"))

ggsave(
  filename = out_png,
  plot     = final,
  width    = FIG_W_MM,
  height   = DENS1_H_MM + DENS2_H_MM + BOX_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)