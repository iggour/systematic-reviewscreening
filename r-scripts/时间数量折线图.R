library(readxl)

df_clean <- read_excel(file.choose())
install.packages("ggplot2")
install.packages("dplyr")
install.packages("tidyr")
library(ggplot2)
library(dplyr)
library(tidyr)
library(dplyr)

plot_data <- df_clean %>%
  filter(year >= 2015, year <= 2025) %>%   # 确保时间范围干净
  group_by(year, method_category) %>%
  summarise(n = n(), .groups = "drop")
library(tidyr)

plot_data <- plot_data %>%
  complete(year = 2015:2025, method_category, fill = list(n = 0))
library(ggplot2)

ggplot(plot_data, aes(x = year, y = n, color = method_category)) +
  geom_line(size = 1.2) +
  geom_point(size = 2) +
  scale_x_continuous(breaks = 2015:2025) +
  labs(
    title = "Annual Trends of AI Methods in Included Studies",
    x = "Year",
    y = "Number of Studies",
    color = "Method Category"
  ) +
  theme_minimal(base_size = 14)
scale_color_manual(values = c(
  "machine_learning" = "#1f77b4",
  "deep_learning" = "#d62728",
  "hybrid" = "#2ca02c"
))
