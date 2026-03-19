#!/usr/bin/env Rscript
# 02_confusion_matrices.R
# ────────────────────────────────────────────────────────────
# Stacked confusion-matrix heat-maps (Depth 1 vs 7) with a
# non-coloured “Total” column and a thicker separator line.

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr")
need_pkg("ggplot2"); need_pkg("tidyr")

suppressPackageStartupMessages({
  library(readr);  library(dplyr)
  library(ggplot2); library(tidyr)
})

# ---------- flexible CSV resolver ---------------------------
csv_path <- function(depth) {
  base <- sprintf("alg_graphrag_d%d_qa_outcome", depth)
  hits <- c(paste0(base, ".csv"), base)
  hit  <- hits[file.exists(hits)]
  if (length(hit)) return(hit[1])
  stop(sprintf("CSV not found for depth %d (searched '%s' in %s)",
               depth, paste(hits, collapse = "', '"), getwd()))
}

# ---------- load & build matrices (+ Totals) ----------------
depths <- c(2,3)

cm_long <- lapply(depths, function(d) {
  df <- read_csv(csv_path(d), show_col_types = FALSE)

  cm      <- table(Actual = df$gold_label,
                   Predicted = df$prediction)
  cm_tot  <- cbind(cm, Total = rowSums(cm))

  as.data.frame(as.table(cm_tot)) |>
    `colnames<-`(c("Actual", "Predicted", "Freq")) |>    # ▲ rename
    mutate(Depth = paste("Depth", d))
}) |>
  bind_rows()

# ---------------- factor ordering ---------------------------
ordered_lab <- c("maybe", "no", "yes")
cm_long$Actual    <- factor(cm_long$Actual,    levels = ordered_lab)
cm_long$Predicted <- factor(cm_long$Predicted,
                            levels = c(ordered_lab, "Total"))

cm_long$FillVal <- ifelse(cm_long$Predicted == "Total", NA, cm_long$Freq)
sep_x <- length(ordered_lab) + 0.5   # 3.5

# ---------- stacked heat-map --------------------------------
p <- ggplot(cm_long, aes(Predicted, Actual, fill = FillVal)) +
  geom_tile(colour = "grey80", size = 0.4) +
  geom_text(aes(label = Freq), size = 5) +
  scale_fill_gradient(low = "white", high = "steelblue",
                      na.value = "white",
                      guide = guide_colourbar(title = "Count")) +
  facet_grid(rows = vars(Depth)) +
  geom_vline(xintercept = sep_x, size = 1.2, colour = "black") +
  theme_minimal(base_size = 14) +
  theme(
    strip.text   = element_text(size = 14, face = "bold"),
    axis.text.x  = element_text(angle = 45, hjust = 1),
    legend.title = element_text(size = 12)
  )

ggsave("02_confusion_matrices.png", plot = p,
       width = 6, height = 8, dpi = 300)

cat("Saved stacked confusion matrices → 02_confusion_matrices.png\n")