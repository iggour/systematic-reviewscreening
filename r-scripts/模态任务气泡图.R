library(readxl)

df_clean <- read_excel(file.choose())
install.packages("ggplot2")
install.packages("dplyr")
install.packages("tidyr")
library(ggplot2)
library(dplyr)
library(tidyr)
library(dplyr)
# ===== 2. 标准化列名（关键！防止列名不匹配）=====
colnames(df_clean) <- tolower(trimws(colnames(df_clean)))

# ===== 3. 检查列是否存在 =====
print(colnames(df_clean))

# ===== 4. 清洗 modality / task =====
df_clean <- df_clean %>%
  mutate(
    modality = trimws(as.character(modality)),
    task = trimws(as.character(task))
  ) %>%
  filter(
    !is.na(modality), modality != "",
    !is.na(task), task != ""
  )

# ===== 5. 生成气泡图数据 =====
plot_data2 <- df_clean %>%
  group_by(modality, task) %>%
  summarise(n = n(), .groups = "drop")

# 👉 强制检查（非常重要）
print(head(plot_data2))
print(nrow(plot_data2))

# ===== 6. 定义颜色 =====
modality_colors <- c(
  "DTI" = "#66c2a5",
  "fMRI" = "#fc8d62",
  "fNIRS" = "#8da0cb",
  "MRI" = "#e78ac3",
  "multimodal" = "#a6d854",
  "NR" = "#ffd92f",
  "PET" = "#e5c494"
)

# ===== 7. 画图 =====
ggplot(plot_data2, aes(x = modality, y = task)) +
  
  geom_point(
    aes(size = n, fill = modality),
    shape = 21,
    stroke = 0,
    alpha = 0.9
  ) +
  
  scale_size(range = c(5, 12)) +
  
  scale_fill_manual(
    values = modality_colors,
    drop = FALSE   # ⭐ 防止类别丢失
  ) +
  
  theme_minimal(base_size = 14) +
  
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1)
  ) +
  
  labs(
    title = "Distribution of Imaging Modalities and Tasks",
    x = "Imaging Modality",
    y = "Task",
    size = "Number of Studies",
    fill = "Modality"
  )