import pandas as pd

# Load slit width file
slit_file = "data/width.xlsx"
df = pd.read_excel(slit_file)

# Reshape from wide to long format
df_long = df.melt(id_vars=["Pipe Category in  NB or  OD or mm"], 
                  var_name="Thickness_Col", value_name="Strip_Width_mm")

# Extract thickness value from column name
df_long["Thickness_mm"] = df_long["Thickness_Col"].str.extract(r"(\d+\.?\d*)").astype(float)

# Apply formula for mass
df_long["Mass_kg"] = 0.0471 * df_long["Strip_Width_mm"] * df_long["Thickness_mm"]

# Clean up
df_long = df_long.rename(columns={"Pipe Category in  NB or  OD or mm": "Pipe_Category"})
df_long = df_long[["Pipe_Category", "Thickness_mm", "Strip_Width_mm", "Mass_kg"]].dropna()

# Save weight sheet
df_long.to_excel("data/weight_sheet.xlsx", index=False)

print("✅ Weight sheet generated: data/weight_sheet.xlsx")
