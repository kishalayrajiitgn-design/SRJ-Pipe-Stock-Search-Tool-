import os, glob, re
import pandas as pd
import streamlit as st

# --- Constants ---
WEIGHT_FILE = "data/weight per pipe (kg).xlsx"

# --- Load weight data ---
def load_weight_data():
    try:
        return pd.read_excel(WEIGHT_FILE)
    except Exception as e:
        st.error(f"Error loading weight file: {e}")
        return None

# --- Find latest stock file ---
def get_latest_stock_file():
    stock_files = glob.glob("data/Stocks*.xlsx")  # match any Stocks(...).xlsx
    if not stock_files:
        return None
    return max(stock_files, key=os.path.getctime)

# --- Load stock data ---
def load_stock_data():
    latest_file = get_latest_stock_file()
    if latest_file and os.path.exists(latest_file):
        return pd.read_excel(latest_file, sheet_name="Table 1"), latest_file
    return None, None

# --- App UI ---
st.title("📊 Pipe Stock Availability Checker")

# Load weight data
weight_df = load_weight_data()
if weight_df is None:
    st.stop()

# Load stock data
stock_df, stock_file = load_stock_data()

if stock_df is None:
    st.warning("⚠️ No stock file found in 'data/' folder.")
    uploaded_file = st.file_uploader("Upload today's stock file", type="xlsx")
    if uploaded_file:
        stock_df = pd.read_excel(uploaded_file, sheet_name="Table 1")
        st.success("✅ Stock file uploaded successfully!")
    else:
        st.stop()
else:
    st.success(f"✅ Using stock file: {os.path.basename(stock_file)}")

# --- User Input ---
st.subheader("🔍 Search Stock")

pipe_input = st.text_input(
    "Enter pipe (e.g. `40x40 1.6mm`, `40x40 18kg`, `20NB 2mm`)"
).strip()

quantity = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

# --- Processing ---
if st.button("Check Availability") and pipe_input:

    # Detect if input contains mm or kg
    thickness_match = re.search(r"([\d.]+)\s*mm", pipe_input.lower())
    weight_match = re.search(r"([\d.]+)\s*kg", pipe_input.lower())

    pipe_size = pipe_input.split()[0]  # first part like 40x40 or 20NB
    thickness = float(thickness_match.group(1)) if thickness_match else None
    weight = float(weight_match.group(1)) if weight_match else None

    st.write(f"🔎 Searching for pipe size: **{pipe_size}**")

    # --- Find weight per pipe ---
    weight_per_pipe = None

    if thickness:
        # Lookup weight from weight_df
        try:
            weight_row = weight_df[
                (weight_df.astype(str).apply(lambda x: pipe_size in x.values, axis=1))
            ]
            if not weight_row.empty:
                if str(thickness) in weight_row.columns:
                    weight_per_pipe = weight_row[str(thickness)].values[0]
        except Exception:
            pass

    elif weight:
        # Reverse lookup: find matching weight column
        try:
            weight_row = weight_df[
                (weight_df.astype(str).apply(lambda x: pipe_size in x.values, axis=1))
            ]
            if not weight_row.empty:
                for col in weight_row.columns[3:]:  # thickness columns
                    if abs(weight_row[col].values[0] - weight) < 0.5:
                        thickness = float(col)
                        weight_per_pipe = weight_row[col].values[0]
                        break
        except Exception:
            pass

    if weight_per_pipe is None:
        st.error("❌ Pipe size or thickness/weight not found in weight table.")
        st.stop()

    # --- Check stock availability ---
    if thickness and str(thickness) in stock_df.columns:
        stock_row = stock_df[
            stock_df.astype(str).apply(lambda x: pipe_size in x.values, axis=1)
        ]
        if not stock_row.empty:
            stock_mt = stock_row[str(thickness)].values[0]  # MT from stock
            stock_kg = stock_mt * 1000
            available_pcs = int(stock_kg / weight_per_pipe)

            if available_pcs >= quantity:
                st.success(
                    f"✅ Available! {available_pcs} pcs in stock. "
                    f"Requested: {quantity} pcs "
                    f"(~{quantity * weight_per_pipe:.2f} kg)"
                )
            else:
                st.warning(
                    f"⚠️ Not enough stock. Only {available_pcs} pcs available, "
                    f"but requested {quantity} pcs."
                )
        else:
            st.error("❌ Pipe size not found in stock sheet.")
    else:
        st.error("❌ Thickness column not found in stock sheet.")


