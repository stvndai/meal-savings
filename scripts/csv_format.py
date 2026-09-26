import pandas as pd

df = pd.read_csv("./recipes_data.csv")

new_df = df.drop(columns=['directions', 'source', 'ingredients', 'site'])
df_reduced = new_df.sample(frac=0.5, random_state=42)
df_reduced = df_reduced.reset_index(drop=True)


print(df_reduced.head())

df_reduced.to_csv("recipes_data_cleaned.csv")
