import pandas as pd
import streamlit as st
import glob
import os

# ----------------------------
# 1. Generate weight.xlsx from width.xlsx (fixed)
# ----------------------------
def generate_weight_file():
    width_file = "data/width.xlsx"
    weight_file = "data/weight.xlsx"

    if not os.path.exists(weight_file):
        df_width = pd.read_excel(width_file)
        df_weight = []

        thickness_cols = df_width.columns[1:]  # All columns except first (Pipe Category)
        for _, row in df_width.iterrows():
            pipe_category = row[0]
            for col in thickness_cols:
                thickness = float(col.split()[2])  # Extract thickness in mm from column header
                width = row[col]
                if pd.notna(width):
                    mass = 0.0471 * width * thickness  # Mass formula
                    df_weight.append({
                        "Pipe Category": pipe_category,
                        "Thickness_mm": thickness,
                        "Weight_kg": mass
                    })

        df_weight = pd.DataFrame(df_weight)
        df_weight.to_excel(weight_file, index=False)
        st.write("weight.xlsx created successfully.")
    else:
        st.write("weight.xlsx already exists.")

# ----------------------------
# 2. Read latest stock file
# ----------------------------
def read_latest_stock():
    stock_files = glob.glob("data/Stocks(*).xlsx")
    if not stock_files:
        st.error("No stock files found in data folder!")
        return None

    latest_file = max(stock_files, key=os.path.getctime)
    df_stock = pd.read_excel(latest_file)
    df_stock.columns = df_stock.columns.str.strip()  # remove spaces
    return df_stock, latest_file

# ----------------------------
# 3. Merge stock with weight data
# ----------------------------
def prepare_stock_data(df_stock, df_weight):
    # Melt stock data (thickness columns to rows)
    thickness_cols = [col for col in df_stock.columns if "Thickness" in col]
    df_melted = df_stock.melt(id_vars=["Pipe Category (Inches)", "Pipe Category (mm / NB / OD)"],
                              value_vars=thickness_cols,
                              var_name="Thickness_mm",
                              value_name="Stock_MT")
    # Convert thickness column to numeric
    df_melted['Thickness_mm'] = df_melted['Thickness_mm'].str.extract(r'([\d\.]+)').astype(float)
    # Merge weight
    df_merged = pd.merge(df_melted, df_weight, how='left', left_on=['Pipe Category (mm / NB / OD)', 'Thickness_mm'],
                         right_on=['Pipe Category', 'Thickness_mm'])
    # Calculate number of pipes
    df_merged['Stock_Pipes'] = (df_merged['Stock_MT'] * 1000) / df_merged['Weight_kg']
    df_merged.fillna(0, inplace=True)
    return df_merged

# ----------------------------
# 4. Streamlit UI
# ----------------------------
st.title("Pipe Sales Search Tool")
st.write("Search pipes by category, thickness, weight, and check stock availability.")

# Generate weight file if not exists
generate_weight_file()

# Load weight data
df_weight = pd.read_excel("data/weight.xlsx")

# Load latest stock
df_stock, latest_file = read_latest_stock()
if df_stock is not None:
    st.write(f"Latest stock file: {os.path.basename(latest_file)}")
    df_data = prepare_stock_data(df_stock, df_weight)

    # Sidebar filters
    pipe_category = st.selectbox("Pipe Category (Inches / NB / OD / mm):",
                                 df_data['Pipe Category (mm / NB / OD)'].unique())
    thickness_range = st.slider("Pipe Thickness Range (mm):", 
                                min_value=float(df_data['Thickness_mm'].min()), 
                                max_value=float(df_data['Thickness_mm'].max()), 
                                value=(1.2, 7.0), step=0.1)
    weight_range = st.slider("Pipe Weight Range (kg, optional):",
                             min_value=float(df_data['Weight_kg'].min()), 
                             max_value=float(df_data['Weight_kg'].max()),
                             value=(0.0, float(df_data['Weight_kg'].max())))
    quantity_required = st.number_input("Quantity Required:", min_value=1, value=10)

    # Filter data
    df_filtered = df_data[df_data['Pipe Category (mm / NB / OD)'] == pipe_category]
    df_filtered = df_filtered[(df_filtered['Thickness_mm'] >= thickness_range[0]) &
                              (df_filtered['Thickness_mm'] <= thickness_range[1])]
    df_filtered = df_filtered[(df_filtered['Weight_kg'] >= weight_range[0]) &
                              (df_filtered['Weight_kg'] <= weight_range[1])]
    
    # Calculate availability
    df_filtered['Available'] = df_filtered['Stock_Pipes'] >= quantity_required
    df_filtered['Quantity_Available'] = df_filtered['Stock_Pipes']

    st.write("Filtered Stock Data:")
    st.dataframe(df_filtered[['Pipe Category (Inches)', 'Pipe Category (mm / NB / OD)',
                              'Thickness_mm', 'Weight_kg', 'Stock_MT', 'Stock_Pipes',
                              'Available', 'Quantity_Available']].sort_values(by='Thickness_mm'))

