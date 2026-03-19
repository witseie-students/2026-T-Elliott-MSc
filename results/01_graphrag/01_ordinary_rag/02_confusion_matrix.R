#!/usr/bin/env Rscript
# 02_confusion_matrix.R
# ────────────────────────────────────────────────────────────
# Confusion-matrix, overall & per-class accuracy for the
# ordinary-RAG run (ordinary_rag_qa_outcome.csv) and a PNG
# heat-map.  Includes a non-coloured “Total” column with a
# thicker separator line.

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr");  need_pkg("ggplot2")

library(readr);  library(dplyr);  library(ggplot2)

# ---------- read data ---------------------------------------
csv_file <- "ordinary_rag_qa_outcome.csv"
if (!file.exists(csv_file))
  stop(paste0("File not found: ", csv_file))

df <- read_csv(csv_file, show_col_types = FALSE)

# ---------- confusion matrix & accuracy ---------------------
cm         <- table(Actual = df$actual_result,
                    Predicted = df$final_result)
row_totals <- rowSums(cm)
cm_tot     <- cbind(cm, Total = row_totals)

overall_acc <- mean(df$final_result == df$actual_result)

cat("Confusion matrix (counts):\n")
print(cm_tot)
cat("\nOverall accuracy:", sprintf("%.2f%%\n\n", overall_acc * 100))

# ---------- per-class conditional accuracy ------------------
class_acc <- diag(cm) / row_totals
for (lbl in names(class_acc)) {
  cat(sprintf("P(correct | actual = %-5s) : %.2f%%\n",
              lbl, class_acc[[lbl]] * 100))
}

# ---------- heat-map PNG ------------------------------------
cm_df <- as.data.frame(as.table(cm_tot))
names(cm_df) <- c("Actual", "Predicted", "Count")

# remove colour for the Total column
cm_df$FillVal <- ifelse(cm_df$Predicted == "Total", NA, cm_df$Count)

# ensure desired column order
pred_levels <- c(setdiff(sort(unique(df$final_result)), "Total"), "Total")
cm_df$Predicted <- factor(cm_df$Predicted, levels = pred_levels)

p <- ggplot(cm_df, aes(Predicted, Actual, fill = FillVal)) +
  geom_tile(color = "grey80", size = 0.4) +
  geom_text(aes(label = Count), size = 5) +
  scale_fill_gradient(
    low = "white",
    high = "steelblue",
    na.value = "white",
    guide = guide_colourbar(title = "Count")
  ) +
  theme_minimal(base_size = 14) +
  theme(
    axis.text.x  = element_text(angle = 45, hjust = 1),
    legend.title = element_text(size = 12)
  ) +
  # thicker separator before Total column
  geom_vline(
    xintercept = length(pred_levels) - 0.5,
    size       = 1.2,
    colour     = "black"
  )

ggsave("01_06_confusion_matrix_ordinary_rag.png",
       plot   = p,
       width  = 6, height = 4, dpi = 300)

cat("\nSaved PNG → 01_06_confusion_matrix_ordinary_rag.png\n")