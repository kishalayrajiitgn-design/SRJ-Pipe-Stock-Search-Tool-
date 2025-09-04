import streamlit as st
import pandas as pd
import glob
import os

# -------------------------
# Load Data
# -------------------------

# Always load the latest stock file
stock_files = glob.glob("data/Stocks(*.xlsx)")
latest_stock_file = max(stock_files, key=os.path.getctime)

# Load stock and weight data
stock_df = pd.read_excel(latest_stock_file, sheet_name="Table 1")
weight_df = pd.read_excel("data/weight_per_pipe.xlsx", sheet_name="Weight per pipe")

# Clean column names (remove spaces, unify types)
stock_df.columns = stock_df.columns.astype(str).str.strip()
weight_df.columns = weight_df.columns.astype(str).str.strip()

# -------------------------
# Helper Functions
# -------------------------

def get_weight_per_pipe(size, thickness):
    """Return weight (kg) per single pipe for given size + thickness"""
    try:
        return weight_df.loc[weight_df["NB Sizes"] == size, str(thickness)].values[0]
    except:
        return None

def get_stock(size, thickness):
    """Return stock (MT) for given size + thickness"""
    try:
        return stock_df.loc[stock_df["PIPE SIZES"] == size, str(thickness)].values[0]
    except:
        return None

def calculate_availability(size, thickness, requested_pieces):
    """Check availability and return stock, requested qty, balance"""
    weight_per_pipe = get_weight_per_pipe(size, thickness)
    stock_mt = get_stock(size, thickness)

    if weight_per_pipe is None or stock_mt is None:
        return None

    stock_kg = stock_mt * 1000
    stock_pieces = stock_kg / weight_per_pipe

    requested_kg = requested_pieces * weight_per_pipe
    requested_mt = requested_kg / 1000

    balance_pieces = stock_pieces - requested_pieces
    balance_kg = stock_kg - requested_kg
    balance_mt = stock_mt - requested_mt

    return {
        "available": requested_pieces <= stock_pieces,
        "stock_pieces": int(stock_pieces),
        "stock_kg": round(stock_kg, 2),
        "stock_mt": round(stock_mt, 2),
        "requested_pieces": requested_pieces,
        "requested_kg": round(requested_kg, 2),
        "requested_mt": round(requested_mt, 2),
        "balance_pieces": int(balance_pieces),
        "balance_kg": round(balance_kg, 2),
        "balance_mt": round(balance_mt, 2)
    }

# -------------------------
# Streamlit UI
# -------------------------

st.title("📦 Pipe Stock Availability Checker")

st.sidebar.header("Search Options")
size = st.sidebar.text_input("Enter Pipe Size (e.g., 40x40, 25 NB, 38.1 OD)")
thickness = st.sidebar.text_input("Enter Thickness (mm, e.g., 1.6, 2.0)")
requested_pieces = st.sidebar.number_input("Enter Requested Pieces", min_value=1, step=1)

if st.sidebar.button("Check Availability"):
    result = calculate_availability(size, thickness, requested_pieces)

    if result is None:
        st.error("❌ No matching record found. Check size or thickness input.")
    else:
        if result["available"]:
            st.success("✅ Stock Available")
        else:
            st.warning("⚠️ Stock Not Sufficient")

        st.write("### Stock Details")
        st.write(f"**Stock**: {result['stock_pieces']} pieces ({result['stock_kg']} kg, {result['stock_mt']} MT)")
        st.write(f"**Requested**: {result['requested_pieces']} pieces ({result['requested_kg']} kg, {result['requested_mt']} MT)")
        st.write(f"**Balance**: {result['balance_pieces']} pieces ({result['balance_kg']} kg, {result['balance_mt']} MT)")

