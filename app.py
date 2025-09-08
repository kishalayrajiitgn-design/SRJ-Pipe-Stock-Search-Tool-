import streamlit as st
import pandas as pd
import os

DATA_DIR = "data"
WIDTH_FILE = os.path.join(DATA_DIR, "width.xlsx")
STOCK_FILE = os.path.join(DATA_DIR, "Stocks(30-08-2025).xlsx")
WEIGHT_FILE = os.path.join(DATA_DIR, "weight.xlsx")

# Step 1: Generate Weight Sheet
def create_weight_sheet():
    width_df = pd.read_excel(WIDTH_FILE)

    # Copy structure
    weight_df = width_df.copy()

    # Loop through thickness columns (all except first col)
    for col in width_df.columns[1:]:
        thickness = float(col.split()[1]) if " " in col else None
        if thickness:
            weight_df[col] = 0.0471 * width_df[col] * thickness

    weight_df.to_excel(WEIGHT_FILE, index=False)
    return weight_df

# Step 2: Merge with Stock Data
def calculate_stock(weight_df):
    stock_df = pd.read_excel(STOCK_FILE)

    # Copy structure
    result_df = stock_df.copy()

    for col in stock_df.columns[2:]:
        if col in weight_df.columns:
            per_pipe_weight = weight_df[col]
            stock_kg = stock_df[col] * 1000  # MT → kg
            result_df[col] = (stock_kg / per_pipe_weight).round(0)

    return result_df

# Streamlit UI
st.title("📊 Pipe Stock Management")

if st.button("Generate Weight Sheet"):
    weight_df = create_weight_sheet()
    st.success("Weight sheet created successfully!")
    st.dataframe(weight_df)

if st.button("Calculate Available Pipes"):
    if not os.path.exists(WEIGHT_FILE):
        st.error("Weight sheet not found! Generate it first.")
    else:
        weight_df = pd.read_excel(WEIGHT_FILE)
        result_df = calculate_stock(weight_df)
        st.success("Stock calculation done!")
        st.dataframe(result_df)
        st.download_button(
            "Download Stock Report",
            result_df.to_excel(index=False, engine="openpyxl"),
            "stock_report.xlsx"
        )


