import streamlit as st
import pandas as pd
import glob
import os

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

latest_stock_file = max(stock_files, key=os.path.getmtime)
df_stock = pd.read_excel(latest_stock_file)
df_stock.columns = df_stock.columns.str.strip()

# -----------------------
# Melt the stock dataframe to long format
# -----------------------
thickness_cols = df_stock.columns[2:]

df_stock_melted = df_stock.melt(
    id_vars=['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)'],
    value_vars=thickness_cols,
    var_name='Thickness_mm',
    value_name='Stock_MT'
)

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
df_mass_melted = df_mass_melted.rename(columns={df_mass.columns[0]: 'Pipe Category (mm / NB / OD)'})

df_merged = pd.merge(df_stock_melted, df_mass_melted, on=['Pipe Category (mm / NB / OD)', 'Thickness_mm'], how='left')

# -----------------------
# Streamlit UI
# -----------------------
st.title("📊 Pipe Stock Search Tool")
st.sidebar.header("🔍 Search Filters")

pipe_category_input = st.sidebar.text_input("Pipe Category (inch/mm/NB/OD)")
thickness_input = st.sidebar.text_input("Pipe Thickness (mm, e.g., 1.2-2.5)")
weight_input = st.sidebar.text_input("Pipe Weight (kg, optional)")
quantity_required = st.sidebar.number_input("Quantity Required", min_value=1, value=1)

# -----------------------
# Filtering
# -----------------------
df_filtered = df_merged.copy()

# Pipe category filter
if pipe_category_input:
    df_filtered = df_filtered[
        (df_filtered['Pipe Category (Inches)'].astype(str).str.contains(pipe_category_input, case=False)) |
        (df_filtered['Pipe Category (mm / NB / OD)'].astype(str).str.contains(pipe_category_input, case=False))
    ]

# Thickness filter
if thickness_input:
    try:
        if '-' in thickness_input:
            t_min, t_max = map(float, thickness_input.split('-'))
            df_filtered = df_filtered[(df_filtered['Thickness_mm'] >= t_min) & (df_filtered['Thickness_mm'] <= t_max)]
        else:
            df_filtered = df_filtered[df_filtered['Thickness_mm'] == float(thickness_input)]
    except:
        st.warning("Invalid thickness input. Use number or range like 1.2-2.5")

# Weight filter
if weight_input:
    try:
        df_filtered = df_filtered[df_filtered['Mass_kg'] == float(weight_input)]
    except:
        st.warning("Invalid weight input. Enter a valid number.")

# -----------------------
# Calculations
# -----------------------
df_filtered['No_of_Pipes_in_Stock'] = (df_filtered['Stock_MT'] * 1000 / df_filtered['Mass_kg']).round(0)
df_filtered['Total_Weight_in_Stock_kg'] = df_filtered['No_of_Pipes_in_Stock'] * df_filtered['Mass_kg']
df_filtered['Total_Weight_Required_kg'] = df_filtered['Mass_kg'] * quantity_required

# Availability status
def availability_status(row):
    if row['No_of_Pipes_in_Stock'] >= quantity_required:
        return "✅ Available"
    elif 0 < row['No_of_Pipes_in_Stock'] < quantity_required:
        return "⚠️ Low Stock"
    else:
        return "❌ Not Available"

df_filtered['Availability_Status'] = df_filtered.apply(availability_status, axis=1)

# -----------------------
# Display Results
# -----------------------
st.subheader("🔹 Search Results")

# Use styled dataframe with colors
def highlight_availability(row):
    if row['Availability_Status'] == "✅ Available":
        return ['background-color: #d4edda']*len(row)
    elif row['Availability_Status'] == "⚠️ Low Stock":
        return ['background-color: #fff3cd']*len(row)
    else:
        return ['background-color: #f8d7da']*len(row)

st.dataframe(
    df_filtered[['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)', 'Thickness_mm',
                 'Mass_kg', 'Stock_MT', 'No_of_Pipes_in_Stock', 'Total_Weight_in_Stock_kg',
                 'Total_Weight_Required_kg', 'Availability_Status']].style.apply(highlight_availability, axis=1)
)

st.write(f"Latest stock file used: {os.path.basename(latest_stock_file)}")
