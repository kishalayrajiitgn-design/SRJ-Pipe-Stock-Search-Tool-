import streamlit as st
import pandas as pd
import glob
import os

# ----------------------------
# Load data
# ----------------------------
DATA_FOLDER = "data"

@st.cache_data
def load_pipe_mass():
    df_mass = pd.read_excel(os.path.join(DATA_FOLDER, "pipe_mass.xlsx"))
    df_mass.columns = df_mass.columns.str.strip()  # remove extra spaces
    return df_mass

@st.cache_data
def load_latest_stock():
    # Get latest stock file based on date in filename
    stock_files = glob.glob(os.path.join(DATA_FOLDER, "Stocks(*).xlsx"))
    if not stock_files:
        st.error("No stock files found in data folder.")
        return None
    latest_file = max(stock_files, key=os.path.getctime)
    df_stock = pd.read_excel(latest_file)
    df_stock.columns = df_stock.columns.str.strip()
    return df_stock, latest_file

df_mass = load_pipe_mass()
df_stock, stock_file = load_latest_stock()

st.title("Pipe Stock Search Tool")
st.write(f"Using Stock File: `{os.path.basename(stock_file)}`")

# ----------------------------
# Preprocess data
# ----------------------------
# Melt pipe_mass
pipe_col_mass = df_mass.columns[0]  # e.g., 'Pipe Category (in mm, NB, or OD)'
df_mass_melted = df_mass.melt(
    id_vars=[pipe_col_mass],
    var_name='Thickness_mm',
    value_name='Mass_kg'
)

# Melt stock file
pipe_col_stock = df_stock.columns[1]  # 'Pipe Category (mm / NB / OD)'
thickness_cols = df_stock.columns[2:]  # all stock columns
df_stock_melted = df_stock.melt(
    id_vars=[df_stock.columns[0], pipe_col_stock],
    value_vars=thickness_cols,
    var_name='Thickness_mm',
    value_name='Stock_MT'
)

# Clean Thickness column
df_stock_melted['Thickness_mm'] = df_stock_melted['Thickness_mm'].str.extract(r'(\d+\.?\d*)').astype(float)
df_mass_melted['Thickness_mm'] = df_mass_melted['Thickness_mm'].astype(float)

# Merge stock and mass
df_merged = pd.merge(
    df_stock_melted,
    df_mass_melted,
    left_on=[pipe_col_stock, 'Thickness_mm'],
    right_on=[pipe_col_mass, 'Thickness_mm'],
    how='left'
)

# Calculate number of pipes and total weight
df_merged['Stock_Kg'] = df_merged['Stock_MT'] * 1000
df_merged['No_of_Pipes'] = df_merged['Stock_Kg'] / df_merged['Mass_kg']

# ----------------------------
# User inputs
# ----------------------------
st.sidebar.header("Search Criteria")
pipe_input = st.sidebar.text_input("Pipe Category (inch/mm/NB/OD):").strip()
thickness_input = st.sidebar.text_input("Thickness (mm, optional):").strip()
weight_input = st.sidebar.text_input("Pipe Weight (kg, optional):").strip()
quantity_required = st.sidebar.number_input("Quantity Required (No. of Pipes):", min_value=0, step=1)

# ----------------------------
# Filter data
# ----------------------------
df_filtered = df_merged.copy()

# Pipe category filter
if pipe_input:
    df_filtered = df_filtered[
        df_filtered[pipe_col_stock].str.contains(pipe_input, case=False, na=False) |
        df_filtered[df_mass.columns[0]].str.contains(pipe_input, case=False, na=False)
    ]

# Thickness filter
if thickness_input:
    try:
        thickness_val = float(thickness_input)
        df_filtered = df_filtered[df_filtered['Thickness_mm'] == thickness_val]
    except:
        pass

# Weight filter
if weight_input:
    try:
        weight_val = float(weight_input)
        df_filtered = df_filtered[df_filtered['Mass_kg'] == weight_val]
    except:
        pass

# ----------------------------
# Display results
# ----------------------------
if not df_filtered.empty:
    df_filtered['Available'] = df_filtered['No_of_Pipes'] >= quantity_required
    df_filtered['Total_Weight_Required'] = df_filtered['Mass_kg'] * quantity_required

    st.subheader("Search Results")
    st.dataframe(df_filtered[[
        df_stock.columns[0], pipe_col_stock, 'Thickness_mm', 'Mass_kg', 'Stock_MT', 'No_of_Pipes',
        'Available', 'Total_Weight_Required'
    ]].sort_values(['Available'], ascending=False))
else:
    st.warning("No matching pipes found.")

st.write("All data is updated daily from the latest stock file.")

