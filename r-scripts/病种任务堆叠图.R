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

top_tasks <- df_clean %>%
  count(task, sort = TRUE) %>%
  slice_head(n = 5) %>%
  pull(task)

df_clean <- df_clean %>%
  mutate(task = ifelse(task %in% top_tasks, task, "other"))

ggplot(heatmap_data, aes(x = disease_category, y = n, fill = task)) +
  geom_bar(stat = "identity", position = "fill") +
  
  theme_minimal(base_size = 14) +
  
  labs(
    title = "Relative Task Composition by Disease Category",
    x = "Disease Category",
    y = "Proportion"
  )