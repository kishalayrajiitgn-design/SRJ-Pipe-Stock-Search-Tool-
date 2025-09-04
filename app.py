import os
import glob
import pandas as pd
import streamlit as st

# --------------------------
# File paths
# --------------------------
DATA_DIR = "data"
WEIGHT_FILE = os.path.join(DATA_DIR, "weight_per_pipe.xlsx")

# --------------------------
# Load weight (fixed file)
# --------------------------
@st.cache_data
def load_weight():
    df = pd.read_excel(WEIGHT_FILE)
    df = df.rename(columns=lambda x: str(x).strip())
    return df

# --------------------------
# Load daily stock (latest file)
# --------------------------
@st.cache_data
def load_stock():
    stock_files = glob.glob(os.path.join(DATA_DIR, "Stocks*.xlsx"))  # FIXED pattern
    if not stock_files:
        st.error(f"❌ No stock file found in `{DATA_DIR}`. Please upload today's file.")
        st.stop()
    latest_file = max(stock_files, key=os.path.getctime)
    stock_df = pd.read_excel(latest_file, header=1)  # skip first header row
    stock_df = stock_df.rename(columns=lambda x: str(x).strip())
    return stock_df, os.path.basename(latest_file)

# --------------------------
# Parse user input
# --------------------------
def parse_input(pipe_input):
    pipe_input = pipe_input.strip().lower().replace('"', 'inch').replace("''", "inch")
    size, thick, weight = None, None, None

    if "mm" in pipe_input:
        if "nb" in pipe_input:
            parts = pipe_input.replace("mm", "").split()
            size = [p for p in parts if "nb" in p][0]
            thick = [p for p in parts if p.replace('.', '', 1).isdigit()][0]
        else:
            parts = pipe_input.split()
            if "mm" in parts[0]:
                size = parts[0].replace("mm", "")
            if len(parts) > 1:
                if "mm" in parts[1]:
                    thick = parts[1].replace("mm", "")
    elif "kg" in pipe_input:
        parts = pipe_input.split()
        size = parts[0]
        weight = parts[1].replace("kg", "")
    else:
        # Example: 25nb 1.6mm or 2x2 18kg
        parts = pipe_input.split()
        if len(parts) >= 2:
            size = parts[0]
            if "mm" in parts[1]:
                thick = parts[1].replace("mm", "")
            elif "kg" in parts[1]:
                weight = parts[1].replace("kg", "")
        else:
            size = pipe_input
    return size.upper(), thick, weight

# --------------------------
# Find weight per pipe
# --------------------------
def get_weight(size, thickness, weight_df, weight=None):
    row = None
    for _, r in weight_df.iterrows():
        if str(r.get("Pipe size in NB", "")).upper() == size.upper() or \
           str(r.get("Pipe size in mm", "")).upper() == size.upper() or \
           str(r.get("Pipe size in Inches", "")).upper() == size.upper() or \
           str(r.get("Pipe size either in inches or mm or NB", "")).upper() == size.upper():
            row = r
            break

    if row is None:
        return None, None

    if thickness:
        try:
            return float(row[thickness]), thickness
        except:
            return None, None

    if weight:  # reverse match by weight
        diffs = {col: abs(float(row[col]) - float(weight)) for col in row.index if col.replace(".", "", 1).isdigit()}
        best_col = min(diffs, key=diffs.get)
        return float(row[best_col]), best_col
    return None, None

# --------------------------
# Find stock availability
# --------------------------
def check_stock(size, thickness, weight_df, stock_df, qty, weight=None):
    wt, used_thick = get_weight(size, thickness, weight_df, weight)
    if wt is None:
        return None, None, None, None

    stock_row = stock_df[stock_df.iloc[:,1].astype(str).str.upper() == size.upper()]
    if stock_row.empty:
        return None, None, None, None

    try:
        stock_mt = float(stock_row[used_thick].values[0])  # in MT
    except:
        return None, None, None, None

    stock_kg = stock_mt * 1000
    pcs_available = stock_kg // wt
    total_req_kg = qty * wt

    return pcs_available, stock_kg, wt, used_thick

# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(page_title="Pipe Stock Checker", layout="wide")
st.title("📊 Pipe Stock Availability Checker")

# Load data
weight_df = load_weight()
stock_df, stock_file = load_stock()
st.sidebar.success(f"✅ Using stock file: {stock_file}")

# User input
pipe_input = st.text_input("Enter pipe (e.g. 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 19.05 OD 1.2mm)")
qty = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

if st.button("🔍 Check Availability"):
    if not pipe_input:
        st.error("Please enter a pipe size")
    else:
        size, thick, wt = parse_input(pipe_input)
        pcs, stock_kg, wt_per_pipe, used_thick = check_stock(size, thick, weight_df, stock_df, qty, wt)

        if pcs is None:
            st.error("❌ Pipe size or thickness/weight not found in weight/stock tables.")
        else:
            if pcs >= qty:
                st.success(f"✅ Stock Available\n\n**{qty} pcs** requested → {qty*wt_per_pipe:.2f} kg\n\nAvailable: {int(pcs)} pcs ({stock_kg:.2f} kg) at thickness {used_thick} mm")
            else:
                st.warning(f"⚠️ Only **{int(pcs)} pcs** available ({stock_kg:.2f} kg) at thickness {used_thick} mm\n\nRequested: {qty} pcs ({qty*wt_per_pipe:.2f} kg)")





