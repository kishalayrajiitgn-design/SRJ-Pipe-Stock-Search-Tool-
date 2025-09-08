import streamlit as st
import pandas as pd
import os
import re

# -------------------------
# File paths
# -------------------------
DATA_DIR = "data"
WIDTH_FILE = os.path.join(DATA_DIR, "width.xlsx")
STOCK_FILE = os.path.join(DATA_DIR, "Stocks(30-08-2025).xlsx")  # replace with latest
WEIGHT_FILE = os.path.join(DATA_DIR, "weight.xlsx")

# -------------------------
# Step 1: Generate Weight Sheet
# -------------------------
def create_weight_sheet():
    width_df = pd.read_excel(WIDTH_FILE)

    # Copy structure for weights
    weight_df = width_df.copy()

    for col in width_df.columns[1:]:  # skip first column (pipe category)
        # Extract numeric thickness value from column name
        match = re.search(r"(\d+(\.\d+)?)\s*mm", col)
        if match:
            thickness = float(match.group(1))
            # Apply formula Mass (kg) = 0.0471 × W × t
            weight_df[col] = 0.0471 * width_df[col] * thickness
        else:
            # Skip columns without thickness info
            weight_df[col] = None

    # Save generated weight sheet
    weight_df.to_excel(WEIGHT_FILE, index=False)
    return weight_df

# -------------------------
# Step 2: Calculate Stock in Number of Pipes
# -------------------------
def calculate_stock(weight_df):
    stock_df = pd.read_excel(STOCK_FILE)

    # Copy stock structure for results
    result_df = stock_df.copy()

    for col in stock_df.columns[2:]:  # skip first two cols (identifiers)
        if col in weight_df.columns:
            per_pipe_weight = weight_df[col]
            stock_kg = stock_df[col] * 1000  # convert MT → kg
            # Avoid division by zero
            result_df[col] = (stock_kg / per_pipe_weight).replace([float("inf"), -float("inf")], 0).fillna(0).round(0)

    return result_df

# -------------------------
# Streamlit UI
# -------------------------
st.title("📊 Pipe Stock Management Tool")

st.markdown("""
This tool calculates **pipe weight per piece (6m fixed)** from strip width and thickness,  
and converts **stock in MT → number of pipes** available.
""")

# Step 1 button
if st.button("1️⃣ Generate Weight Sheet"):
    if os.path.exists(WIDTH_FILE):
        weight_df = create_weight_sheet()
        st.success("Weight sheet created successfully ✅")
        st.dataframe(weight_df)
    else:
        st.error(f"File not found: {WIDTH_FILE}")

# Step 2 button
if st.button("2️⃣ Calculate Available Pipes"):
    if not os.path.exists(WEIGHT_FILE):
        st.error("Weight sheet not found! Please generate it first.")
    elif not os.path.exists(STOCK_FILE):
        st.error(f"Stock file not found: {STOCK_FILE}")
    else:
        weight_df = pd.read_excel(WEIGHT_FILE)
        result_df = calculate_stock(weight_df)
        st.success("Stock calculation completed ✅")
        st.dataframe(result_df)

        # Download option
        st.download_button(
            "⬇️ Download Stock Report",
            result_df.to_excel(index=False, engine="openpyxl"),
            "stock_report.xlsx"
        )



