# 10_inferred_vs_ordinary.R
# ════════════════════════════════════════════════════════════════════════════
# Same visual layout as 09_inferred_vs_ordinary.R **but** the data now include
# every Rank ≤ 5 neighbour for each abstract (i.e. “Top-5” instead of Rank-1).
#
# PANELS (top → bottom)
#   1. Density (facet by relationship type, coloured by answer)
#   2. Density (overlay: Extracted vs Inferred, answer-agnostic)
#   3. Pie chart (share of Top-5 rows that are Extracted vs Inferred)
#   4. Six box-plots (Extracted/Inferred × Yes/Maybe/No)
#
#  • Y-axis on both density plots is fixed at 0-7.
#  • Console prints per-bucket percentages relative to the **expected maximum
#    of 1 750 rows** (350 abstracts × 5 neighbours).
#
#  • Input  : 09_question_cosines_inferred.csv   (same directory)
#  • Output : 10_inferred_vs_ordinary.png        (same directory)
# ════════════════════════════════════════════════════════════════════════════

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2);  library(patchwork)
  library(scales)
})

# ─────────────────────────────────────────────────────────────────────────────
#  I/O
# ─────────────────────────────────────────────────────────────────────────────
csv_file <- "09_question_cosines_inferred.csv"
out_png  <- "10_inferred_vs_ordinary.png"
if (!file.exists(csv_file))
  stop("Missing file: ", csv_file, call. = FALSE)

# ─────────────────────────────────────────────────────────────────────────────
#  FIGURE GEOMETRY (mm)
# ─────────────────────────────────────────────────────────────────────────────
FIG_W_MM  <- 180
DENS1_H_MM <-  85
DENS2_H_MM <-  60
PIE_H_MM   <-  50
BOX_H_MM   <-  45
DPI        <- 300

# ─────────────────────────────────────────────────────────────────────────────
#  LOAD  &  FILTER   (Top-5 rows only)
# ─────────────────────────────────────────────────────────────────────────────
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    answer            = tolower(trimws(answer)),
    inferred_flag     = ifelse(tolower(inferred) == "true", "Inferred", "Extracted")
  ) %>%
  filter(rank <= 5,                                  # ← keep Top-5
         answer %in% c("yes","maybe","no"),
         !is.na(cosine_similarity))

if (nrow(df) == 0)
  stop("No Rank ≤ 5 rows with answers yes/maybe/no.", call. = FALSE)

# factor orders --------------------------------------------------------------
df$answer        <- factor(df$answer,        levels = c("yes","maybe","no"), ordered = TRUE)
df$inferred_flag <- factor(df$inferred_flag, levels = c("Extracted","Inferred"), ordered = TRUE)

# ─────────────────────────────────────────────────────────────────────────────
#  COUNTS  &  PERCENTAGES
# ─────────────────────────────────────────────────────────────────────────────
TOTAL_EXPECTED <- 350 * 5    # every abstract contributes ≤ 5 rows

cnt_detailed <- df %>%
                  count(inferred_flag, answer, name = "n") %>%
                  mutate(pct = n / TOTAL_EXPECTED * 100)

message("─ Percentages of the 1 750 expected Top-5 rows ─")
cnt_detailed %>%
  arrange(inferred_flag, answer) %>%
  mutate(label = sprintf("%-10s | %-3s : %5.1f %%", inferred_flag, toupper(answer), pct)) %>%
  pull(label) %>%
  writeLines()

cnt_pie <- cnt_detailed %>%
             group_by(inferred_flag) %>%
             summarise(n = sum(n), .groups = "drop") %>%
             mutate(pct = n / TOTAL_EXPECTED)

message("\n─ Extracted vs Inferred share (Top-5 rows) ─")
cnt_pie %>%
  mutate(label = sprintf("%-9s : %5.1f %%", inferred_flag, pct*100)) %>%
  pull(label) %>%
  writeLines()

# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR MAPS
# ─────────────────────────────────────────────────────────────────────────────
ans_cols  <- c("yes"   = "#1f77b4",
               "maybe" = "#ffdf00",
               "no"    = "#d62728")
type_cols <- c("Extracted" = "#1f77b4",
               "Inferred"  = "#2ca02c")

alph     <- 0.35
Y_MAX    <- 7
adjust_k <- 0.4

# ─────────────────────────────────────────────────────────────────────────────
#  DENSITY 1  – FACET BY TYPE, COLOURED BY ANSWER
# ─────────────────────────────────────────────────────────────────────────────
p_dens1 <- ggplot(df, aes(x = cosine_similarity, fill = answer)) +
  geom_density(alpha = alph, colour = "black",
               adjust = adjust_k, linewidth = 0.35) +
  facet_grid(inferred_flag ~ .) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0)) +
  scale_y_continuous(limits = c(0, Y_MAX), expand = c(0,0)) +
  scale_fill_manual(values = ans_cols, name = NULL) +
  labs(x = NULL, y = "Density",
       title = "Top-5 similarity by answer group") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "top",
        strip.text.y     = element_text(face = "bold"))

# ─────────────────────────────────────────────────────────────────────────────
#  DENSITY 2  – EXTRACTED vs INFERRED OVERLAY
# ─────────────────────────────────────────────────────────────────────────────
p_dens2 <- ggplot(df, aes(x = cosine_similarity, colour = inferred_flag, fill = inferred_flag)) +
  geom_density(alpha = 0.35,
               adjust = adjust_k, linewidth = 0.7) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0)) +
  scale_y_continuous(limits = c(0, Y_MAX), expand = c(0,0)) +
  scale_colour_manual(values = type_cols, name = NULL) +
  scale_fill_manual(values = type_cols,   name = NULL) +
  labs(x = NULL, y = "Density",
       title = "Extracted vs Inferred (Top-5, all answers)") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "top")

# ─────────────────────────────────────────────────────────────────────────────
#  PIE CHART  – TYPE SHARE
# ─────────────────────────────────────────────────────────────────────────────
p_pie <- ggplot(cnt_pie, aes(x = "", y = pct, fill = inferred_flag)) +
  geom_col(width = 1, colour = "black") +
  coord_polar("y") +
  geom_text(aes(label = percent(pct, accuracy = 0.1)),
            position = position_stack(vjust = 0.5), size = 3.2) +
  scale_fill_manual(values = type_cols, name = NULL) +
  labs(title = "Extracted vs Inferred share (Top-5)") +
  theme_void(base_size = 11) +
  theme(plot.title  = element_text(hjust = 0.5, face = "bold"),
        legend.position = "none")

# ─────────────────────────────────────────────────────────────────────────────
#  BOX & WHISKERS  – SIX GROUPS
# ─────────────────────────────────────────────────────────────────────────────
df <- df %>% mutate(group = paste(inferred_flag, answer, sep = " – "))
group_levels <- c("Extracted – yes", "Extracted – maybe", "Extracted – no",
                  "Inferred – yes",  "Inferred – maybe",  "Inferred – no")
df$group <- factor(df$group, levels = group_levels)

p_box <- ggplot(df, aes(x = cosine_similarity, y = group, fill = answer)) +
  geom_boxplot(colour = "black",
               width  = 0.55,
               outlier.shape = 16, outlier.size = 1.1,
               linewidth = 0.35) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0),
                     name   = "Cosine similarity (0 – 1)") +
  scale_y_discrete(NULL) +
  scale_fill_manual(values = ans_cols, guide = "none") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank())

# ─────────────────────────────────────────────────────────────────────────────
#  COMBINE  &  SAVE
# ─────────────────────────────────────────────────────────────────────────────
final_plot <- p_dens1 /
              p_dens2 /
              p_pie   /
              p_box   +
  plot_layout(heights = c(DENS1_H_MM, DENS2_H_MM, PIE_H_MM, BOX_H_MM)) &
  theme(plot.margin = margin(4,4,4,4, "mm"))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = FIG_W_MM,
  height   = DENS1_H_MM + DENS2_H_MM + PIE_H_MM + BOX_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)