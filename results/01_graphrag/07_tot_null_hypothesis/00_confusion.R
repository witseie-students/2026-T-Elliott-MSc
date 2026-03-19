#!/usr/bin/env Rscript
# 00_confusion.R
# ═════════════════════════════════════════════════════════════
# Build a confusion-matrix (with an extra “Total” column),
# print per-class & overall accuracies, and save a tidy heat-map.
#
#  • Default CSV  : tot_graphrag_null_d1.csv          ⟵ edit here if you like
#  • PNG output   : 00_confusion_matrix_tot_null.png
#
# You can still override the CSV via the command-line, e.g.:
#   Rscript 00_confusion.R  tot_graphrag_null_d3.csv
# ─────────────────────────────────────────────────────────────

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr"); need_pkg("dplyr"); need_pkg("ggplot2")

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(ggplot2)
})

# ---------- locate CSV --------------------------------------
args      <- commandArgs(trailingOnly = TRUE)
csv_file  <- if (length(args) >= 1) args[1] else "tot_graphrag_null_d2.csv"
if (!file.exists(csv_file))
  stop(paste0("File not found: ", csv_file))

# ---------- read data ---------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE)

# ---------- confusion matrix --------------------------------
cm          <- table(Actual = df$gold_label,
                     Predicted = df$prediction)
row_totals  <- rowSums(cm)
cm_tot      <- cbind(cm, Total = row_totals)

# ---------- accuracies --------------------------------------
overall_acc <- mean(df$prediction == df$gold_label)
class_acc   <- diag(cm) / row_totals

cat("Confusion matrix (counts):\n")
print(cm_tot)
cat("\nOverall accuracy :", sprintf("%.2f%%", overall_acc * 100), "\n\n")

for (lbl in rownames(cm)) {
  cat(sprintf("P(correct | actual = %-7s) : %.2f%%\n",
              lbl, class_acc[[lbl]] * 100))
}

# ---------- heat-map PNG ------------------------------------
cm_df           <- as.data.frame(as.table(cm_tot))
names(cm_df)    <- c("Actual", "Predicted", "Count")
cm_df$FillVal   <- ifelse(cm_df$Predicted == "Total", NA, cm_df$Count)

# move “Total” column to far right
pred_levels     <- c(setdiff(colnames(cm_tot), "Total"), "Total")
cm_df$Predicted <- factor(cm_df$Predicted, levels = pred_levels)

p <- ggplot(cm_df, aes(Predicted, Actual, fill = FillVal)) +
  geom_tile(colour = "grey80", size = 0.4) +
  geom_text(aes(label = Count), size = 5) +
  scale_fill_gradient(low = "white", high = "steelblue",
                      na.value = "white",
                      guide = guide_colourbar(title = "Count")) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text.x  = element_text(angle = 45, hjust = 1),
    legend.title = element_text(size = 12)
  ) +
  # thick divider before “Total”
  geom_vline(xintercept = length(pred_levels) - 0.5,
             size = 1.2, colour = "black")

png_out <- "00_confusion_matrix_tot_null.png"
ggsave(png_out, plot = p, width = 6, height = 4, dpi = 300)
cat("\nSaved PNG →", png_out, "\n")