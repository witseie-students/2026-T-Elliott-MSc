# --------------------------------------------------------------
#  Bar plot of year-on-year PubMed additions, 2010–
#  Input : PubMed_totals_by_publication_year.csv
#  Output: pubmed_yearly_additions_2010.pdf   (160 mm × 55 mm)
# --------------------------------------------------------------

# 1  Packages ---------------------------------------------------
library(readr)   # CSV I/O
library(dplyr)   # wrangling
library(ggplot2) # plotting
library(scales)  # comma axis labels

# 2  Read & tidy ------------------------------------------------
totals <- read_csv(
  "PubMed_totals_by_publication_year.csv",
  show_col_types = FALSE
) |>
  select(-1)                                               # drop row label

df <- data.frame(
  Year         = as.integer(names(totals)),
  TotalRecords = as.numeric(totals[1, ])
) |>
  arrange(Year)                                            # earliest → latest

# 3  Compute year-on-year Δ ------------------------------------
df <- df |>
  mutate(NewRecords = TotalRecords - lag(TotalRecords, default = 0)) |>
  filter(Year >= 2010)                                     # keep 2010+

# 4  Plot -------------------------------------------------------
p <- ggplot(df, aes(Year, NewRecords)) +
  geom_col(fill = "grey40", width = 0.9) +
  theme_bw() +
  labs(
    x = "Publication year (2010 – 2022)",
    y = "New PubMed records"
  ) +
  scale_y_continuous(labels = comma, expand = c(0, 0)) +
  theme(
    text         = element_text(family = "Times"),
    axis.text.x  = element_text(size = rel(0.7), angle = 90, vjust = 0.5),
    axis.text.y  = element_text(size = rel(0.75)),
    axis.title   = element_text(size = rel(0.8)),
    panel.grid.minor = element_blank()
  )

# 5  Save -------------------------------------------------------
ggsave(
  filename = "pubmed_yearly_additions_2010.pdf",
  plot     = p,
  units    = "mm",
  width    = 160,
  height   = 55,
  bg       = "white"
)

# --------------------------------------------------------------
#  End of script
# --------------------------------------------------------------
