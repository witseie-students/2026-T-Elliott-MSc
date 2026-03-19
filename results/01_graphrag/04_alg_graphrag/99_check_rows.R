#!/usr/bin/env Rscript
# 99_check_rows.R
# ────────────────────────────────────────────────────────────
# For each ALG-GraphRAG depth-CSV (d1 … d7) list the PubMed rows
# missing from that result and emit them in *CSV-ready* form with
# sensible default values plus the mean timing stats for the file.

# ---------- helper: install-if-missing ----------------------
need_pkg <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE))
    install.packages(pkg, repos = "https://cloud.r-project.org")
}
need_pkg("readr");  need_pkg("dplyr");  need_pkg("purrr")

suppressPackageStartupMessages({
  library(readr);  library(dplyr);  library(purrr)
})

# ---------- load gold standard ------------------------------
file_gold <- "PUBMED_QA2.csv"
if (!file.exists(file_gold))
  stop("Cannot find PUBMED_QA2.csv in working directory: ", getwd())

gold <- read_csv(file_gold, show_col_types = FALSE) %>%
  mutate(pubmed_id  = as.character(pubid),
         gold_label = tolower(final_decision)) %>%
  select(pubmed_id, question, gold_label)

gold_ids <- gold$pubmed_id

# ---------- parameters --------------------------------------
depths <- 1:7
placeholder_paragraph <-
  "There was no information returned from the database that matches that question."

# ---------- book-keeping containers -------------------------
missing_all_depths <- list()

# ============================================================== #
#                    main per-depth loop                         #
# ============================================================== #
for (d in depths) {
  res_file <- sprintf("alg_graphrag_d%d_qa_outcome.csv", d)

  if (!file.exists(res_file)) {
    cat("\nDepth", d, "→", res_file, "NOT FOUND – treated as all rows missing.\n")
    mean_times <- c(t_embed = NA, t_graph = NA, t_llm = NA, t_total = NA)
    present_ids <- character(0)
  } else {
    res <- read_csv(res_file, show_col_types = FALSE) %>%
           mutate(pubmed_id = as.character(pubmed_id))

    mean_times <- res %>%
      summarise(across(c(t_embed, t_graph, t_llm, t_total), mean, na.rm = TRUE)) %>%
      round(2) %>%
      as.list()

    present_ids <- res$pubmed_id
  }

  miss_ids <- setdiff(gold_ids, present_ids)
  missing_all_depths[[as.character(d)]] <- miss_ids

  cat(
    sprintf("\n───────────────── Depth %d │ missing rows: %d ─────────────────\n",
            d, length(miss_ids))
  )

  if (length(miss_ids)) {
    gold %>%
      filter(pubmed_id %in% miss_ids) %>%
      arrange(pubmed_id) %>%
      rowwise() %>%
      mutate(
        paragraph   = placeholder_paragraph,
        prediction  = "maybe",
        is_correct  = ifelse(gold_label == "maybe", "True", "False"),
        t_embed     = sprintf("%.2f", mean_times$t_embed),
        t_graph     = sprintf("%.2f", mean_times$t_graph),
        t_llm       = sprintf("%.2f", mean_times$t_llm),
        t_total     = sprintf("%.2f", mean_times$t_total),
        csv_row = paste(
          pubmed_id,
          question,
          sprintf('"%s"', paragraph),  # ensure quotes around paragraph
          prediction,
          gold_label,
          is_correct,
          t_embed, t_graph, t_llm, t_total,
          sep = ","
        )
      ) %>%
      pull(csv_row) %>%
      walk(cat, "\n")
  } else {
    cat("✓ All PubMed IDs covered for depth", d, "\n")
  }
}

# ---------- common missing across *all* depths ---------------
common_missing <- Reduce(intersect, missing_all_depths)

cat("\n════════════════ Missing from EVERY depth (", length(common_missing), ") ════════════════\n", sep = "")
if (length(common_missing)) {
  gold %>%
    filter(pubmed_id %in% common_missing) %>%
    arrange(pubmed_id) %>%
    mutate(
      paragraph   = placeholder_paragraph,
      prediction  = "maybe",
      is_correct  = ifelse(gold_label == "maybe", "True", "False"),
      # dummy times – we use depth-1 means for illustration, adapt as needed
      csv_row = paste(
        pubmed_id,
        question,
        sprintf('"%s"', paragraph),
        prediction,
        gold_label,
        is_correct,
        "", "", "", "",          # leave time fields blank / fill later
        sep = ","
      )
    ) %>%
    pull(csv_row) %>%
    walk(cat, "\n")
} else {
  cat("✓ Every PubMed ID appears in at least one depth result.\n")
}