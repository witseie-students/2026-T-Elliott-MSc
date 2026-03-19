# 99_bottom_rank.R
# ─────────────────────────────────────────────────────────────────────────────
# Show the 20 *worst* (lowest-similarity) rank-1 neighbours, including PubMed
# IDs.  Expects the three-column CSV produced by the Django command:
#
#       pubid , rank , cosine_similarity
#
# Run (from the same directory as question_cosines.csv):
#       Rscript 99_bottom_rank.R
#
# Required packages:
#   install.packages(c("readr","dplyr","knitr"))
# ─────────────────────────────────────────────────────────────────────────────

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(knitr)
})

csv_file <- "question_cosines.csv"
if (!file.exists(csv_file))
  stop("Missing file: ", csv_file, call. = FALSE)

# ── load --------------------------------------------------------------------
df <- read_csv(csv_file, show_col_types = FALSE) %>%
  mutate(
    row_id            = row_number(),            # running row index (1 … n)
    question_idx      = ceiling(row_id / 20L),   # every 20 rows = new query
    rank              = as.integer(rank),
    cosine_similarity = as.numeric(cosine_similarity)
  ) %>%
  filter(!is.na(rank), !is.na(cosine_similarity))

if (nrow(df) == 0)
  stop("No rows read from CSV.", call. = FALSE)

# ── bottom-20 among rank-1 rows --------------------------------------------
bottom20 <- df %>%
  filter(rank == 1L) %>%
  arrange(cosine_similarity) %>%
  slice_head(n = 20L) %>%
  select(pubid, question_idx, cosine_similarity)

# ── pretty table ------------------------------------------------------------
cat("\n🔻  Bottom-20 rank-1 neighbours (lowest cosine similarity)\n\n")
print(
  kable(
    bottom20,
    col.names = c("PubMed ID", "Question #", "Cosine similarity"),
    digits    = 4,
    align     = c("r","r","r")
  )
)
cat("\n")