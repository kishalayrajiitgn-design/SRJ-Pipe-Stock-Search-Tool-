import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ------------------------
# Step 1: Generate weight.xlsx from width.xlsx (fixed file)
# ------------------------
def generate_weight_file():
    width_file = 'data/width.xlsx'
    weight_file = 'data/weight.xlsx'

    if not os.path.exists(weight_file):
        # Read width.xlsx
        df_width = pd.read_excel(width_file)

        # Extract thickness columns
        thickness_cols = df_width.columns[1:]  # all except first column (Pipe Category)
        new_rows = []

        for index, row in df_width.iterrows():
            pipe_category = row[df_width.columns[0]]
            for col in thickness_cols:
                thickness = float(col.split()[-2])  # get thickness value from column name
                width = row[col]
                if pd.notna(width) and width != 0:
                    mass = 0.0471 * width * thickness  # mass for 6m pipe
                    new_rows.append({
                        "Pipe Category": pipe_category,
                        "Thickness_mm": thickness,
                        "Width_mm": width,
                        "Weight_kg": mass
                    })

        df_weight = pd.DataFrame(new_rows)
        df_weight.to_excel(weight_file, index=False)
    return weight_file

# ------------------------
# Step 2: Load daily stock file
# ------------------------
def load_stock_file():
    stock_folder = 'data'
    # find latest stock file in folder
    stock_files = [f for f in os.listdir(stock_folder) if f.startswith('Stocks') and f.endswith('.xlsx')]
    if not stock_files:
        st.error("No stock files found in data folder.")
        return None
    # pick latest by modified time
    stock_files.sort(key=lambda x: os.path.getmtime(os.path.join(stock_folder, x)), reverse=True)
    latest_stock_file = os.path.join(stock_folder, stock_files[0])
    df_stock = pd.read_excel(latest_stock_file)
    return df_stock

# ------------------------
# Step 3: Streamlit UI
# ------------------------
st.title("Pipe Sales Search Tool")
st.write("Search pipes by category, thickness, weight, and check stock availability.")

# Load weight and stock
weight_file = generate_weight_file()
df_weight = pd.read_excel(weight_file)
df_stock = load_stock_file()
if df_stock is None:
    st.stop()

# Input filters
pipe_category_input = st.text_input("Pipe Category (Inches / NB / OD / mm):")
thickness_range = st.slider("Pipe Thickness Range (mm):", 1.2, 7.0, (1.2, 7.0), step=0.1)
weight_range = st.text_input("Pipe Weight Range (kg, optional):")
required_qty = st.number_input("Quantity Required:", min_value=1, step=1)

# Filter by category
if pipe_category_input:
    df_filtered = df_weight[df_weight['Pipe Category'].str.contains(pipe_category_input, case=False, na=False)]
else:
    df_filtered = df_weight.copy()

# Filter by thickness
df_filtered = df_filtered[(df_filtered['Thickness_mm'] >= thickness_range[0]) &
                          (df_filtered['Thickness_mm'] <= thickness_range[1])]

# Filter by weight if given
if weight_range:
    try:
        weight_from, weight_to = [float(x.strip()) for x in weight_range.split('-')]
        df_filtered = df_filtered[(df_filtered['Weight_kg'] >= weight_from) & (df_filtered['Weight_kg'] <= weight_to)]
    except:
        st.warning("Weight range format incorrect. Use format: min-max (e.g., 10-50)")

# Merge with stock
df_stock_melted = df_stock.melt(id_vars=['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)'],
                                var_name='Thickness_col', value_name='Stock_MT')

# Map thickness columns to float
df_stock_melted['Thickness_mm'] = df_stock_melted['Thickness_col'].str.extract(r'(\d+\.?\d*)').astype(float)

# Merge on pipe category and thickness
df_merged = pd.merge(df_filtered,
                     df_stock_melted,
                     left_on=['Pipe Category', 'Thickness_mm'],
                     right_on=['Pipe Category (mm / NB / OD)', 'Thickness_mm'],
                     how='left')

# Calculate number of pipes
df_merged['Stock_Pipes'] = (df_merged['Stock_MT'] * 1000 / df_merged['Weight_kg']).fillna(0).astype(int)
df_merged['Available'] = df_merged['Stock_Pipes'] >= required_qty

# Display results
st.subheader("Search Results")
st.dataframe(df_merged[['Pipe Category', 'Thickness_mm', 'Weight_kg', 'Stock_MT', 'Stock_Pipes', 'Available']].sort_values(by='Thickness_mm'))

# ------------------------
# Step 4: Download option
# ------------------------
st.download_button(
    label="Download Filtered Data",
    data=df_merged.to_excel(index=False),
    file_name='filtered_pipes.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)



