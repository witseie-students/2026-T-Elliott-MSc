# 09_inferred_vs_ordinary.R
# ════════════════════════════════════════════════════════════════════════════
# Rank-1 neighbour similarity analysis
#
# OUTPUT PANELS (top → bottom)
# ─────────────────────────────────────────────────────────────────────────────
# 1. Density facet   : Extracted vs Inferred, coloured by answer (Yes/Maybe/No)
# 2. Density overlay : Extracted vs Inferred (answer-agnostic)
# 3. Pie chart       : Share of abstracts that return an Extracted vs Inferred
#                      Rank-1 neighbour (expressed as % of the 350 total)
# 4. Box & whiskers  : Six groups (Extracted/Inferred × Yes/Maybe/No)
#
#  • Y-axis on both density plots is fixed at 0 – 7 for easy comparison.
#  • Console prints per-bucket percentages **and** a two-way table for the pie.
#
#  • Input  : 09_question_cosines_inferred.csv   (same directory)
#  • Output : 09_inferred_vs_ordinary.png        (same directory)
# ════════════════════════════════════════════════════════════════════════════

suppressPackageStartupMessages({
  library(readr);   library(dplyr);   library(ggplot2);   library(patchwork)
  library(scales)   # for percent format in pie labels
})

# ─────────────────────────────────────────────────────────────────────────────
#  I/O
# ─────────────────────────────────────────────────────────────────────────────
csv_file <- "09_question_cosines_inferred.csv"
out_png  <- "09_inferred_vs_ordinary.png"
if (!file.exists(csv_file))
  stop("Missing file: ", csv_file, call. = FALSE)

# ─────────────────────────────────────────────────────────────────────────────
#  FIGURE GEOMETRY (mm)
# ─────────────────────────────────────────────────────────────────────────────
FIG_W_MM  <- 180   # total width
DENS1_H_MM <-  85  # density facet
DENS2_H_MM <-  60  # density overlay
PIE_H_MM   <-  50  # pie chart
BOX_H_MM   <-  45  # box & whiskers
DPI        <- 300

# ─────────────────────────────────────────────────────────────────────────────
#  LOAD  &  FILTER
# ─────────────────────────────────────────────────────────────────────────────
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    answer            = tolower(trimws(answer)),
    inferred_flag     = ifelse(tolower(inferred) == "true", "Inferred", "Extracted")
  ) %>%
  filter(rank == 1, answer %in% c("yes","maybe","no"), !is.na(cosine_similarity))

if (nrow(df) == 0)
  stop("No Rank-1 rows with answers yes/maybe/no.", call. = FALSE)

# factor orders --------------------------------------------------------------
df$answer        <- factor(df$answer,        levels = c("yes","maybe","no"), ordered = TRUE)
df$inferred_flag <- factor(df$inferred_flag, levels = c("Extracted","Inferred"), ordered = TRUE)

# ─────────────────────────────────────────────────────────────────────────────
#  COUNTS  &  PERCENTAGES
# ─────────────────────────────────────────────────────────────────────────────
TOTAL_PARA <- 350

# detailed 3×2 table (printed)
cnt_detailed <- df %>%
                  count(inferred_flag, answer, name = "n") %>%
                  mutate(pct = n / TOTAL_PARA * 100)

message("─ Percentages of 350 abstracts (Rank-1 rows) ─")
cnt_detailed %>%
  arrange(inferred_flag, answer) %>%
  mutate(label = sprintf("%-10s | %-3s : %5.1f %%", inferred_flag, toupper(answer), pct)) %>%
  pull(label) %>%
  writeLines()

# summary table for pie
cnt_pie <- cnt_detailed %>%
             group_by(inferred_flag) %>%
             summarise(n = sum(n), .groups = "drop") %>%
             mutate(pct = n / TOTAL_PARA)

# print pie percentages
message("\n─ Extracted vs Inferred (all answers) ─")
cnt_pie %>%
  mutate(label = sprintf("%-9s : %5.1f %%", inferred_flag, pct*100)) %>%
  pull(label) %>%
  writeLines()

# ─────────────────────────────────────────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────────────────────────────────────────
ans_cols  <- c("yes"   = "#1f77b4",   # blue
               "maybe" = "#ffdf00",   # yellow
               "no"    = "#d62728")   # red
type_cols <- c("Extracted" = "#1f77b4",   # blue
               "Inferred"  = "#2ca02c")   # green

alph <- 0.35
Y_MAX <- 10         # fixed ceiling for both density plots
adjust_k <- 0.4     # bandwidth adjust factor

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
       title = "Rank-1 similarity by answer group") +
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
       title = "Extracted vs Inferred (all answers)") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "top")

# ─────────────────────────────────────────────────────────────────────────────
#  PIE CHART  – TYPE SHARE
# ─────────────────────────────────────────────────────────────────────────────
pie_labels <- cnt_pie %>%
                mutate(label = paste0(inferred_flag, "\n", percent(pct, accuracy = 0.1)))

p_pie <- ggplot(cnt_pie, aes(x = "", y = pct, fill = inferred_flag)) +
  geom_col(width = 1, colour = "black") +
  coord_polar("y") +
  geom_text(aes(label = percent(pct, accuracy = 0.1)),
            position = position_stack(vjust = 0.5), size = 3.3) +
  scale_fill_manual(values = type_cols, name = NULL) +
  labs(x = NULL, y = NULL,
       title = "Extracted vs Inferred share") +
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
               width = 0.55,
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