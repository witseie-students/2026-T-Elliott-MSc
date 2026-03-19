#!/usr/bin/env Rscript

# 04_full_results.R
# =============================================================================
# Reads alg_graphrag_d1_qa_outcome.csv ... alg_graphrag_d7_qa_outcome.csv (same directory),
# computes per-class Precision / Recall / F1 for yes/no/maybe, plus Overall (weighted) Total,
# and prints 3 tables to the terminal (Precision table, Recall table, F1 table).
#
# Assumes CSV columns include at least: prediction, gold_label
# =============================================================================

classes <- c("yes", "no", "maybe")

# ---- helpers ----------------------------------------------------------------

safe_div <- function(num, den) {
  ifelse(den == 0, NA_real_, num / den)
}

compute_metrics_from_cm <- function(cm) {
  # cm is a 3x3 matrix with rownames = gold, colnames = prediction
  supports <- rowSums(cm)
  total_n <- sum(supports)

  precision <- setNames(rep(NA_real_, length(classes)), classes)
  recall    <- setNames(rep(NA_real_, length(classes)), classes)
  f1        <- setNames(rep(NA_real_, length(classes)), classes)

  for (c in classes) {
    tp <- cm[c, c]
    fp <- sum(cm[, c]) - tp
    fn <- sum(cm[c, ]) - tp

    p <- safe_div(tp, tp + fp)
    r <- safe_div(tp, tp + fn)
    f <- ifelse(is.na(p) | is.na(r) | (p + r) == 0, NA_real_, 2 * p * r / (p + r))

    precision[c] <- p
    recall[c]    <- r
    f1[c]        <- f
  }

  # Overall weighted by gold-label support (i.e., class frequency in the dataset)
  # Replace NA with 0 for safety; with your data it should not occur.
  w <- supports / total_n
  overall_precision <- sum(ifelse(is.na(precision), 0, precision) * w)
  overall_recall    <- sum(ifelse(is.na(recall),    0, recall)    * w)
  overall_f1        <- sum(ifelse(is.na(f1),        0, f1)        * w)

  list(
    precision = precision,
    recall = recall,
    f1 = f1,
    total = c(precision = overall_precision, recall = overall_recall, f1 = overall_f1),
    supports = supports,
    n = total_n
  )
}

format_table <- function(df) {
  # Force 2 decimal places and align
  df_fmt <- df
  for (j in seq_len(ncol(df_fmt))) {
    if (is.numeric(df_fmt[[j]])) {
      df_fmt[[j]] <- sprintf("%.2f", df_fmt[[j]])
    }
  }
  df_fmt
}

print_section <- function(title, df) {
  cat("\n", title, "\n", sep = "")
  cat(paste(rep("=", nchar(title)), collapse = ""), "\n", sep = "")
  print(format_table(df), row.names = FALSE, right = TRUE)
}

# ---- locate files ------------------------------------------------------------

files <- list.files(
  path = ".",
  pattern = "^alg_graphrag_d[1-7]_qa_outcome\\.csv$",
  full.names = TRUE
)

if (length(files) == 0) {
  stop("No files found matching alg_graphrag_d[1-7]_qa_outcome.csv in this directory.")
}

# Sort by depth number
get_depth <- function(f) {
  m <- regmatches(f, regexec("d([1-7])_qa_outcome\\.csv$", f))
  as.integer(m[[1]][2])
}
depths <- sapply(files, get_depth)
files <- files[order(depths)]
depths <- depths[order(depths)]

# ---- compute tables ----------------------------------------------------------

# We will build three data.frames with rows = depth 1..7, cols = yes/no/maybe/total
precision_tbl <- data.frame(Depth = depths, Yes = NA_real_, No = NA_real_, Maybe = NA_real_, Total = NA_real_)
recall_tbl    <- data.frame(Depth = depths, Yes = NA_real_, No = NA_real_, Maybe = NA_real_, Total = NA_real_)
f1_tbl        <- data.frame(Depth = depths, Yes = NA_real_, No = NA_real_, Maybe = NA_real_, Total = NA_real_)

for (i in seq_along(files)) {
  df <- read.csv(files[i], stringsAsFactors = FALSE)

  if (!all(c("prediction", "gold_label") %in% names(df))) {
    stop(sprintf("File %s is missing required columns: prediction and/or gold_label", files[i]))
  }

  pred <- tolower(trimws(df$prediction))
  gold <- tolower(trimws(df$gold_label))

  # Keep only valid labels
  keep <- gold %in% classes & pred %in% classes
  gold <- gold[keep]
  pred <- pred[keep]

  if (length(gold) == 0) {
    stop(sprintf("File %s has no valid rows with gold_label/prediction in {yes,no,maybe}", files[i]))
  }

  cm <- table(
    factor(gold, levels = classes),
    factor(pred, levels = classes)
  )
  cm <- as.matrix(cm)
  rownames(cm) <- classes
  colnames(cm) <- classes

  m <- compute_metrics_from_cm(cm)

  # store as percentages
  precision_tbl$Yes[i]   <- 100 * m$precision["yes"]
  precision_tbl$No[i]    <- 100 * m$precision["no"]
  precision_tbl$Maybe[i] <- 100 * m$precision["maybe"]
  precision_tbl$Total[i] <- 100 * m$total["precision"]

  recall_tbl$Yes[i]   <- 100 * m$recall["yes"]
  recall_tbl$No[i]    <- 100 * m$recall["no"]
  recall_tbl$Maybe[i] <- 100 * m$recall["maybe"]
  recall_tbl$Total[i] <- 100 * m$total["recall"]

  f1_tbl$Yes[i]   <- 100 * m$f1["yes"]
  f1_tbl$No[i]    <- 100 * m$f1["no"]
  f1_tbl$Maybe[i] <- 100 * m$f1["maybe"]
  f1_tbl$Total[i] <- 100 * m$total["f1"]
}

# ---- print results -----------------------------------------------------------

print_section("Precision (%) by hop-depth", precision_tbl)
print_section("Recall (%) by hop-depth", recall_tbl)
print_section("F1-score (%) by hop-depth", f1_tbl)

cat("\nDone.\n")