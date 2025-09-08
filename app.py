import streamlit as st
import pandas as pd
import glob
import os
from datetime import datetime

# -----------------------
# Load Excel Data
# -----------------------

DATA_FOLDER = "data"

# Load pipe mass file
pipe_mass_file = os.path.join(DATA_FOLDER, "pipe_mass.xlsx")
df_mass = pd.read_excel(pipe_mass_file)
df_mass.columns = df_mass.columns.str.strip()

# Get latest stock file automatically based on date in filename
stock_files = glob.glob(os.path.join(DATA_FOLDER, "Stocks(*).xlsx"))
if not stock_files:
    st.error("No stock files found in the data folder.")
    st.stop()

# Sort by modified time to get latest
latest_stock_file = max(stock_files, key=os.path.getmtime)
df_stock = pd.read_excel(latest_stock_file)
df_stock.columns = df_stock.columns.str.strip()

# -----------------------
# Melt the stock dataframe to long format
# -----------------------
thickness_cols = df_stock.columns[2:]  # columns starting from 3rd are thickness columns

df_stock_melted = df_stock.melt(
    id_vars=['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)'],
    value_vars=thickness_cols,
    var_name='Thickness_mm',
    value_name='Stock_MT'
)

# Extract thickness number from column name
df_stock_melted['Thickness_mm'] = df_stock_melted['Thickness_mm'].str.extract(r'([\d.]+)').astype(float)

# -----------------------
# Merge with pipe mass
# -----------------------
df_mass_melted = df_mass.melt(
    id_vars=[df_mass.columns[0]],
    var_name='Thickness_mm',
    value_name='Mass_kg'
)
df_mass_melted['Thickness_mm'] = df_mass_melted['Thickness_mm'].astype(float)

# Rename pipe category column to match
df_mass_melted = df_mass_melted.rename(columns={df_mass.columns[0]: 'Pipe Category (mm / NB / OD)'})

# Merge mass with stock
df_merged = pd.merge(df_stock_melted, df_mass_melted, on=['Pipe Category (mm / NB / OD)', 'Thickness_mm'], how='left')

# -----------------------
# Streamlit UI
# -----------------------
st.title("Pipe Stock Search Tool")

st.sidebar.header("Search Filters")

pipe_category_input = st.sidebar.text_input("Pipe Category (inch/mm/NB/OD)")
thickness_input = st.sidebar.text_input("Pipe Thickness (mm, e.g., 1.2-2.5)")
weight_input = st.sidebar.text_input("Pipe Weight (kg) - Optional")
quantity_required = st.sidebar.number_input("Quantity Required", min_value=1, value=1)

# Filter by pipe category
if pipe_category_input:
    df_filtered = df_merged[
        (df_merged['Pipe Category (Inches)'].astype(str).str.contains(pipe_category_input, case=False)) |
        (df_merged['Pipe Category (mm / NB / OD)'].astype(str).str.contains(pipe_category_input, case=False))
    ]
else:
    df_filtered = df_merged.copy()

# Filter by thickness
if thickness_input:
    if '-' in thickness_input:
        t_min, t_max = map(float, thickness_input.split('-'))
        df_filtered = df_filtered[(df_filtered['Thickness_mm'] >= t_min) & (df_filtered['Thickness_mm'] <= t_max)]
    else:
        df_filtered = df_filtered[df_filtered['Thickness_mm'] == float(thickness_input)]

# Filter by weight if provided
if weight_input:
    weight_val = float(weight_input)
    df_filtered = df_filtered[df_filtered['Mass_kg'] == weight_val]

# Calculate number of pipes and stock weight
df_filtered['No_of_Pipes_in_Stock'] = (df_filtered['Stock_MT'] * 1000 / df_filtered['Mass_kg']).round(0)
df_filtered['Total_Weight_in_Stock_kg'] = df_filtered['No_of_Pipes_in_Stock'] * df_filtered['Mass_kg']
df_filtered['Total_Weight_Required_kg'] = df_filtered['Mass_kg'] * quantity_required
df_filtered['Available'] = df_filtered['No_of_Pipes_in_Stock'] >= quantity_required

# Show results
st.subheader("Search Results")
st.dataframe(df_filtered[
    ['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)', 'Thickness_mm',
     'Mass_kg', 'Stock_MT', 'No_of_Pipes_in_Stock', 'Total_Weight_in_Stock_kg',
     'Available', 'Total_Weight_Required_kg']
])

st.write(f"Latest stock file used: {os.path.basename(latest_stock_file)}")
