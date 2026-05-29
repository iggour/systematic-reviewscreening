library(readxl)

df_clean <- read_excel(file.choose())
library(ggplot2)
library(dplyr)

df_clean <- df_clean %>%
  mutate(
    disease_lower = tolower(disease),
    disease_category = case_when(
      
      grepl("autism|asd|adhd|development|neurodevelopment|delay|dyslexia|cognitive|psychiatric|schizophrenia|anxiety|depression|tourette|behavior|psychopathology|preterm|fetal|trajectory", disease_lower) ~ "NDD",
      
      grepl("tumor|glioma|malformation|dysplasia|lesion|hydrocephalus|ventriculomegaly|cortical|lissencephaly|polymicrogyria|hemorrhage|stroke|hypoxic|encephalopathy|cerebral palsy|brain injury", disease_lower) ~ "CBM",
      
      grepl("metabolic|mitochond|enzyme|rasopathies|leukodystrophy|scn1a", disease_lower) ~ "IEM",
      
      TRUE ~ "Other"
    )
  )

heatmap_data <- df_clean %>%
  group_by(disease_category, task) %>%
  summarise(n = n(), .groups = "drop")

ggplot(heatmap_data, aes(x = task, y = disease_category, fill = n)) +
  geom_tile(color = "white") +
  
  scale_fill_viridis_c(
    option = "plasma",
    begin = 0.15,
    end = 0.9
  )
  
  theme_minimal(base_size = 14) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1)
  ) +
  
  labs(
    title = "Task Distribution Across Disease Categories",
    x = "Task",
    y = "Disease Category",
    fill = "Number of Studies"
  )