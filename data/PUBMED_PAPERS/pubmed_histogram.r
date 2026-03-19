## pubmed_histogram_captioned.R
##
## @online{nlm_eutils_2025,
##   author  = {National Library of Medicine},
##   title   = {Entrez Programming Utilities – esearch.fcgi},
##   year    = {2025},
##   url     = {https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi},
##   note    = {Accessed: 2025-05-30}
## }
##
## Generates a 160 mm × 90 mm, 600 dpi bar chart showing the annual number
## of new PubMed citations (1965–2025), y-axis in millions, caption embedded.
##
## ── Run ──
##   Rscript pubmed_histogram_captioned.R
##
## ── Output ──
##   pubmed_histogram_captioned.png
##

library(ggplot2)
library(scales)     # for label_number()
library(readr)

# ── 1. Load data ───────────────────────────────────────────────────────────────
df <- if (requireNamespace("readr", quietly = TRUE)) {
  readr::read_csv(
    "pubmed_yearly_counts.csv",
    col_types = readr::cols(
      year = readr::col_integer(),
      new_pubmed_citations = readr::col_integer()
    )
  )
} else {
  read.csv("pubmed_yearly_counts.csv",
           colClasses = c("integer", "integer"))
}

df$year <- factor(df$year, levels = df$year)  # keep chronological order

# ── 2. Axis limit helper ───────────────────────────────────────────────────────
y_limit <- max(df$new_pubmed_citations) * 1.1  # 10 % head-room

# ── 3. Build plot ──────────────────────────────────────────────────────────────
plt <- ggplot(df, aes(x = year, y = new_pubmed_citations)) +
  theme_bw() +
  geom_col(
    fill      = "skyblue",
    color     = "black",
    linewidth = 0.25,           # thinner outline
    width     = 0.8
  ) +
  labs(
    x       = "Calendar Year",
    y       = "New PubMed citations (millions)",
    caption = "Annual number of new PubMed citations loaded between 1965–2025."
  ) +
  scale_x_discrete(
    expand = c(0, 0),
    breaks = levels(df$year)[seq(1, length(levels(df$year)), by = 5)]
  ) +
  scale_y_continuous(
    limits = c(0, y_limit),
    expand = c(0, 0),
    labels = label_number(scale = 1e-6, accuracy = 0.1, suffix = " M")
  ) +
  theme(
    text             = element_text(family = "Times", size = 12),
    axis.title.x     = element_text(size = 12, margin = margin(t = 15)),
    axis.text.x      = element_text(size = 10, angle = 45, hjust = 1),
    axis.title.y     = element_text(size = 12),
    axis.text.y      = element_text(size = 10),
    panel.grid.major = element_line(color = "grey80", linewidth = 0.5),
    panel.grid.minor = element_line(color = "grey90", linewidth = 0.25),
    plot.caption     = element_text(size = 10, hjust = 0.5, margin = margin(t = 10))  # centred
  )

# ── 4. Save ────────────────────────────────────────────────────────────────────
ggsave(
  filename = "pubmed_histogram_captioned.png",
  plot     = plt,
  units    = "mm",
  width    = 160,
  height   = 90,
  dpi      = 600,
  bg       = "white"
)

message("✓ Saved pubmed_histogram_captioned.png (160 mm × 90 mm, 600 dpi, y-axis in millions)")
