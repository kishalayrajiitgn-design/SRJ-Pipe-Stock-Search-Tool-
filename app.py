# app.py
import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="Daily Pipe Stock Dashboard", layout="wide")
st.title("📊 Daily Pipe Stock Dashboard")

# --- Load Width Data (fixed) ---
width_file = os.path.join("data", "width.xlsx")
if not os.path.exists(width_file):
    st.error("❌ Width data file not found in data/ folder.")
    st.stop()
width_df = pd.read_excel(width_file)
width_df = width_df.fillna(0)  # Replace empty widths with 0

# --- Load Latest Stock File ---
stock_files = glob.glob("data/Stocks(*.xlsx)")
if not stock_files:
    st.error("❌ No stock file found in data/ folder.")
    st.stop()

latest_stock_file = max(stock_files, key=os.path.getctime)  # latest by creation time
stock_df = pd.read_excel(latest_stock_file)
stock_df = stock_df.fillna(0)  # Replace empty stock with 0

st.markdown(f"**Latest stock file loaded:** `{os.path.basename(latest_stock_file)}`")

# --- Prepare Weight Sheet ---
# Weight formula: Mass (kg) = 0.0471 * Width(mm) * Thickness(mm)
thickness_cols = width_df.columns[1:]  # skip first column (Pipe Category)
weight_df = width_df.copy()
for col in thickness_cols:
    weight_df[col] = 0.0471 * width_df[col] * float(col.split()[0])  # col name like 'Width of pipe corresponding to Thickness 1.2 mm'

# --- Helper Functions ---
def get_stock(pipe_category, thickness_col):
    """Return stock in MT from stock_df for given pipe_category and thickness column"""
    row = stock_df[stock_df.iloc[:, 1] == pipe_category]  # 2nd column: mm/NB/OD
    if row.empty:
        return 0
    return float(row[thickness_col].values[0])

def get_mass(pipe_category, thickness_col):
    """Return mass (kg per pipe) from weight_df"""
    row = weight_df[weight_df.iloc[:, 0] == pipe_category]  # 1st column: pipe category
    if row.empty:
        return 0
    return float(row[thickness_col].values[0])

def mt_to_pipes(stock_mt, mass_per_pipe):
    if mass_per_pipe <= 0:
        return 0
    return (stock_mt * 1000) / mass_per_pipe

# --- Sidebar Filters ---
st.sidebar.header("🔎 Search Pipe")
pipe_search = st.sidebar.text_input("Pipe Category (Inches / NB / OD / mm)")
thickness_search = st.sidebar.text_input("Pipe Thickness (mm)")
weight_search = st.sidebar.text_input("Pipe Weight (kg)")

# --- Filter Data ---
results = []

for idx, row in stock_df.iterrows():
    pipe_category = row[1]  # mm / NB / OD
    if pipe_search:
        if pipe_search.lower() not in str(pipe_category).lower():
            continue
    for col in thickness_cols:
        thickness_value = float(col.split()[0])  # 1.2, 1.4, ...
        if thickness_search:
            try:
                thickness_min = float(thickness_search.split("-")[0])
                thickness_max = float(thickness_search.split("-")[1])
                if not (thickness_min <= thickness_value <= thickness_max):
                    continue
            except:
                if float(thickness_search) != thickness_value:
                    continue
        mass_per_pipe = get_mass(pipe_category, col)
        stock_mt = get_stock(pipe_category, col)
        num_pipes = mt_to_pipes(stock_mt, mass_per_pipe)
        if weight_search:
            if float(weight_search) != mass_per_pipe:
                continue
        results.append({
            "Pipe Category": pipe_category,
            "Thickness (mm)": thickness_value,
            "Mass per Pipe (kg)": round(mass_per_pipe, 2),
            "Stock (MT)": stock_mt,
            "Number of Pipes": int(num_pipes)
        })

# --- Display Results ---
if results:
    display_df = pd.DataFrame(results)
    st.dataframe(display_df.sort_values(by=["Pipe Category", "Thickness (mm)"]))
else:
    st.info("No matching pipe found for the given search criteria.")

st.markdown("---")
st.write("Developed by: Kishalay Raj")


