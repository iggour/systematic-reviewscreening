library(readxl)

df_clean <- read_excel(file.choose())
install.packages("ggplot2")
install.packages("dplyr")
install.packages("tidyr")
library(ggplot2)
library(dplyr)
library(tidyr)
install.packages("rnaturalearth")
install.packages("rnaturalearthdata")
install.packages("sf")
library(rnaturalearth)
library(rnaturalearthdata)
library(sf)

df_clean <- df_clean %>%
  separate_rows(country, sep = "/")  #（可选但推荐）

plot_map_data2 <- df_clean %>%
  mutate(country = recode(country,
                          "USA" = "United States of America",
                          "UK" = "United Kingdom",
                          "NR" = NA_character_
  )) %>%
  filter(!is.na(country)) %>%
  group_by(country) %>%
  summarise(n = n(), .groups = "drop")

world <- ne_countries(scale = "medium", returnclass = "sf")
map_data2 <- world %>%
  left_join(plot_map_data2, by = c("name" = "country"))
ggplot(map_data2) +
  geom_sf(aes(fill = n), color = "white") +
  scale_fill_viridis_c(
    option = "plasma",
    begin = 0.15,
    end = 0.9,
    na.value = "grey90"
  )
  theme_minimal() +
  labs(
    title = "Global Distribution of AI Studies",
    fill = "Number of Studies"
  )