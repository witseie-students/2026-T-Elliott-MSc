# 07_density_answers.R  – three-colour overlay with labelled thresholds
# ────────────────────────────────────────────────────────────────────────────
# • Rank-1 neighbours only
# • Density overlay (Yes / Maybe / No)  +  matching box-and-whiskers
# • Dashed thresholds at 0.661 (Q₁), 0.600 (un-labelled), 0.543 (Q₃)
# • Arrow heads point *toward* their dashed lines
# • Output: 01_answer_groups_density.png
# ────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2)
  library(patchwork);               library(scales)
})

# ── I/O --------------------------------------------------------------------
csv_file <- "question_cosines.csv"
out_png  <- "01_02_answer_groups_density_v2.png"
if (!file.exists(csv_file)) stop("Missing file: ", csv_file, call. = FALSE)

# ── figure geometry --------------------------------------------------------
FIG_W_MM  <- 180
DENS_H_MM <-  85
BOX_H_MM  <-  40
DPI       <- 300

# thresholds & labels -------------------------------------------------------
THR1 <- 0.661                      # Q₁ of STS-B 3–4
THR0 <- 0.600                      # mid-threshold
THR2 <- 0.543                      # Q₃ of STS-B 1–2
LAB1 <- "Q\u2081 of STS-B Bin 3"
LAB2 <- "Q\u2083 of STS-B Bin 1"

# ── load & keep Rank-1 rows -----------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    rank              = as.integer(rank),
    cosine_similarity = pmin(pmax(as.numeric(cosine_similarity), 0), 1),
    answer            = tolower(trimws(answer))
  ) %>%
  filter(rank == 1, answer %in% c("yes","maybe","no"),
         !is.na(cosine_similarity))

if (nrow(df) == 0) stop("No Rank-1 rows with answers yes/maybe/no.", call. = FALSE)

# ── factor order & colours --------------------------------------------------
ans_levels <- c("yes","maybe","no")
df$answer  <- factor(df$answer, levels = ans_levels, ordered = TRUE)

fills <- c("yes"   = "#1f77b4",   # blue
           "maybe" = "#ffdf00",   # yellow
           "no"    = "#d62728")   # red
alph  <- 0.35

# ── density panel ----------------------------------------------------------
adjust_k  <- 0.4
dens_obj  <- density(df$cosine_similarity, adjust = adjust_k, from = 0, to = 1)
dens_ymax <- 8                                 # fixed ceiling for clarity

# label & arrow anchor coordinates
lab1_x <- THR1 + 0.03 ; lab1_y <- dens_ymax * 0.92
lab2_x <- THR2 - 0.03 ; lab2_y <- dens_ymax * 0.80
off    <- 0.01                                 # arrow shaft length

p_dens <- ggplot(df, aes(x = cosine_similarity, fill = answer,
                         linetype = answer)) +
  geom_density(alpha = alph, colour = "black",
               adjust = adjust_k, linewidth = 0.35) +
  geom_vline(xintercept = c(THR1, THR0, THR2),
             linetype = "dashed", linewidth = 0.5) +

  # arrow & label for THR1  (arrow ←) ---------------------------------------
  annotate("segment",
           x = lab1_x - off, xend = THR1,
           y = lab1_y,       yend = lab1_y,
           linewidth = 0.4,
           arrow = arrow(length = unit(3, "pt"), type = "closed")) +
  annotate("text",
           x = lab1_x, y = lab1_y,
           label = LAB1, hjust = 0, vjust = 0.5, size = 3) +

  # arrow & label for THR2  (arrow →) ---------------------------------------
  annotate("segment",
           x = lab2_x + off, xend = THR2,
           y = lab2_y,       yend = lab2_y,
           linewidth = 0.4,
           arrow = arrow(length = unit(3, "pt"), type = "closed")) +
  annotate("text",
           x = lab2_x, y = lab2_y,
           label = LAB2, hjust = 1, vjust = 0.5, size = 3) +

  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0)) +
  scale_y_continuous(limits = c(0, dens_ymax), expand = c(0,0)) +
  scale_fill_manual(values = fills, name = NULL) +
  scale_linetype_manual(values = c("solid","22","44"), name = NULL) +
  labs(
       x = NULL, y = "Density") +
  theme_bw(base_size = 11) +
  theme(plot.title       = element_text(hjust = 0.5, face = "bold"),
        panel.grid.minor = element_blank(),
        legend.position  = "top")

# ── box-and-whisker panel ---------------------------------------------------
p_box <- ggplot(df, aes(x = cosine_similarity, y = answer, fill = answer)) +
  geom_boxplot(colour = "black",
               width  = 0.5,
               outlier.shape = 16, outlier.size = 1.1,
               linewidth = 0.35) +
  geom_vline(xintercept = c(THR1, THR0, THR2),
             linetype = "dashed", linewidth = 0.5) +
  scale_x_continuous(limits = c(0,1), breaks = seq(0,1,0.1),
                     expand = c(0,0),
                     name   = "Cosine similarity (0 – 1)") +
  scale_y_discrete(limits = ans_levels,
                   labels = tools::toTitleCase(ans_levels)) +
  scale_fill_manual(values = fills, guide = "none") +
  labs(subtitle = "Horizontal box-and-whiskers by answer") +
  theme_bw(base_size = 11) +
  theme(plot.subtitle    = element_text(hjust = 0.5),
        panel.grid.minor = element_blank())

# ── assemble & save --------------------------------------------------------
final_plot <- p_dens / p_box +
  plot_layout(heights = c(DENS_H_MM, BOX_H_MM)) &
  theme(plot.margin = margin(4,4,4,4,"mm"))

ggsave(
  filename = out_png,
  plot     = final_plot,
  width    = FIG_W_MM,
  height   = DENS_H_MM + BOX_H_MM,
  units    = "mm",
  dpi      = DPI,
  bg       = "white"
)

message("✅  Figure saved to: ", out_png)