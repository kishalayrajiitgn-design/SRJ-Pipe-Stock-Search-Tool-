import pandas as pd
import streamlit as st
import numpy as np
import os

st.set_page_config(page_title="Pipe Sales Search Tool", layout="wide")

# ---------------------------
# Paths to your data
# ---------------------------
WIDTH_FILE = "data/width.xlsx"
STOCK_FILE = "data/latest_stock.xlsx"  # always rename daily stock to this
WEIGHT_FILE = "data/weight.xlsx"

# ---------------------------
# 1. Prepare weight.xlsx from width.xlsx
# ---------------------------
def generate_weight_file(width_file=WIDTH_FILE, weight_file=WEIGHT_FILE):
    df = pd.read_excel(width_file)
    # Melt width data: Thickness as variable
    df_melted = df.melt(id_vars=['Pipe Category (NB/OD/mm)'], 
                        var_name='Thickness_mm', value_name='Width_mm')
    # Extract numeric thickness
    df_melted['Thickness_mm'] = df_melted['Thickness_mm'].str.extract(r'([\d.]+)').astype(float)
    # Calculate mass per pipe (6 m length, density 7850 kg/m3)
    df_melted['Mass_kg'] = 0.0471 * df_melted['Width_mm'] * df_melted['Thickness_mm']
    df_melted.to_excel(weight_file, index=False)
    return df_melted

if not os.path.exists(WEIGHT_FILE):
    df_weight = generate_weight_file()
else:
    df_weight = pd.read_excel(WEIGHT_FILE)

# ---------------------------
# 2. Load daily stock
# ---------------------------
if not os.path.exists(STOCK_FILE):
    st.warning("Latest stock file not found. Upload today's stock as 'latest_stock.xlsx' in data folder.")
    st.stop()

df_stock = pd.read_excel(STOCK_FILE)
# Melt stock data for easier search
thickness_cols = [col for col in df_stock.columns if "Thickness" in col]
df_stock_melted = df_stock.melt(id_vars=['Pipe Category (Inches)', 'Pipe Category (mm/NB/OD)'], 
                                value_vars=thickness_cols,
                                var_name='Thickness_mm',
                                value_name='Stock_MT')
df_stock_melted['Thickness_mm'] = df_stock_melted['Thickness_mm'].str.extract(r'([\d.]+)').astype(float)

# Merge with weight.xlsx to get mass per pipe
df_data = pd.merge(df_stock_melted, df_weight, 
                   left_on=['Pipe Category (mm/NB/OD)', 'Thickness_mm'],
                   right_on=['Pipe Category (NB/OD/mm)', 'Thickness_mm'],
                   how='left')
df_data['No_of_Pipes'] = np.where(df_data['Mass_kg']>0, df_data['Stock_MT']*1000/df_data['Mass_kg'], 0)
df_data['Available'] = np.where(df_data['No_of_Pipes']>0, 'Yes', 'No')

# ---------------------------
# 3. Streamlit UI
# ---------------------------
st.title("Pipe Sales Search Tool")
st.markdown("Search pipes by category, thickness, weight, and check stock availability.")

# Filters
pipe_category_input = st.text_input("Enter Pipe Category (Inches / NB / OD / mm)", "")
thickness_min, thickness_max = st.slider("Thickness (mm)", 1.2, 7.0, (1.2, 7.0))
weight_min, weight_max = st.slider("Weight per pipe (kg)", 0.0, 1000.0, (0.0, 1000.0))
quantity_required = st.number_input("Quantity Required", min_value=1, value=1)

# Filter data
df_filtered = df_data.copy()
if pipe_category_input:
    df_filtered = df_filtered[df_filtered['Pipe Category (Inches)'].str.contains(pipe_category_input, case=False, na=False) |
                              df_filtered['Pipe Category (mm/NB/OD)'].str.contains(pipe_category_input, case=False, na=False)]

df_filtered = df_filtered[(df_filtered['Thickness_mm'] >= thickness_min) &
                          (df_filtered['Thickness_mm'] <= thickness_max)]
df_filtered = df_filtered[(df_filtered['Mass_kg'] >= weight_min) &
                          (df_filtered['Mass_kg'] <= weight_max)]

# Calculate stock based on requested quantity
df_filtered['Can_Fulfill'] = np.where(df_filtered['No_of_Pipes'] >= quantity_required, 'Yes', 'No')

# Display results
st.dataframe(df_filtered[['Pipe Category (Inches)', 'Pipe Category (mm/NB/OD)', 'Thickness_mm', 
                          'Mass_kg', 'Stock_MT', 'No_of_Pipes', 'Available', 'Can_Fulfill']].reset_index(drop=True))

st.markdown(f"Total records found: {len(df_filtered)}")


