import streamlit as st
import pandas as pd
import glob
import os
import re

# --------------------------
# Config
# --------------------------
DATA_DIR = "data"
WEIGHT_FILE = os.path.join(DATA_DIR, "weight_per_pipe.xlsx")

# --------------------------
# Load daily stock (latest file)
# --------------------------
def load_stock():
    stock_files = glob.glob(os.path.join(DATA_DIR, "Stocks(*.xlsx)"))
    if not stock_files:
        st.error("❌ No stock file found in /data. Please upload today's file.")
        return None
    latest_file = max(stock_files, key=os.path.getctime)
    st.write(f"✅ Using stock file: {os.path.basename(latest_file)}")

    df = pd.read_excel(latest_file, sheet_name="Table 1")
    df = df.dropna(how="all")
    return df

# --------------------------
# Load weight mapping (fixed file)
# --------------------------
def load_weight():
    df = pd.read_excel(WEIGHT_FILE)
    df = df.dropna(how="all")
    return df

# --------------------------
# Normalize input
# --------------------------
def parse_input(user_input):
    user_input = user_input.strip().lower()

    # Extract numbers + units
    qty_match = re.search(r"(\d+)\s*pcs?", user_input)
    if qty_match:
        qty = int(qty_match.group(1))
    else:
        qty = None

    # Detect thickness (mm)
    thick_match = re.search(r"(\d+(\.\d+)?)\s*mm", user_input)
    thickness = float(thick_match.group(1)) if thick_match else None

    # Detect weight (kg)
    kg_match = re.search(r"(\d+(\.\d+)?)\s*kg", user_input)
    weight = float(kg_match.group(1)) if kg_match else None

    # Detect size (NB, inch, mm, or xx×yy)
    size = None
    if "nb" in user_input:
        size = re.search(r"(\d+\s*nb)", user_input)
        size = size.group(1).replace(" ", "") if size else None
    elif "x" in user_input:  # Square or Rectangular like 40x40, 80x40
        size = re.search(r"(\d+\s*x\s*\d+)", user_input)
        size = size.group(1).replace(" ", "") if size else None
    elif "od" in user_input:  # OD in mm
        size = re.search(r"(\d+(\.\d+)?)\s*od", user_input)
        size = size.group(1) + " OD" if size else None
    elif '"' in user_input:  # Inch size
        size = re.search(r"(\d+(\.\d+)?)\s*\"", user_input)
        size = size.group(1) + '"' if size else None
    else:  # Pure mm like 33.4 or 101.6
        size = re.search(r"(\d+(\.\d+)?)", user_input)
        size = size.group(1) if size else None

    return size, thickness, weight, qty

# --------------------------
# Find per pipe weight
# --------------------------
def find_per_pipe_weight(weight_df, size, thickness, weight):
    # Match size row (inch, mm, or NB)
    match_row = weight_df.apply(lambda row: any(
        str(size).replace(" ", "") in str(val).replace(" ", "")
        for val in row.values
    ), axis=1)

    if not match_row.any():
        return None, None

    row = weight_df[match_row].iloc[0]

    # Case 1: thickness provided → get weight
    if thickness:
        if str(thickness) in row.index.astype(str):
            return row[str(thickness)], thickness

    # Case 2: weight provided → match closest thickness
    if weight:
        numeric_cols = [c for c in row.index if re.match(r"^\d+(\.\d+)?$", str(c))]
        weights = row[numeric_cols].astype(float)
        closest_col = weights.sub(weight).abs().idxmin()
        return row[closest_col], float(closest_col)

    return None, None

# --------------------------
# Check stock availability
# --------------------------
def check_stock(stock_df, size, thickness, per_pipe_wt, qty_required):
    # Match row
    row_match = stock_df.apply(lambda row: str(size).replace(" ", "").lower() in str(row.values).replace(" ", "").lower(), axis=1)
    if not row_match.any():
        return None, None, None

    row = stock_df[row_match].iloc[0]

    if str(thickness) not in row.index.astype(str):
        return None, None, None

    stock_mt = row[str(thickness)]
    stock_kg = stock_mt * 1000  # MT → kg
    max_pcs = stock_kg / per_pipe_wt if per_pipe_wt else 0

    available = qty_required <= max_pcs
    return available, max_pcs, stock_kg

# --------------------------
# Streamlit UI
# --------------------------
st.title("📊 Pipe Stock Availability Checker")

stock_df = load_stock()
weight_df = load_weight()

if stock_df is not None and weight_df is not None:
    user_input = st.text_input("Enter pipe (e.g. 40x40 1.6mm, 25NB 18kg, 1\" 2mm):")
    qty_required = st.number_input("Enter required quantity (pcs):", min_value=1, value=1)

    if user_input:
        size, thickness, weight, _ = parse_input(user_input)
        st.write(f"🔎 Parsed → Size: {size}, Thickness: {thickness}, Weight: {weight}")

        per_pipe_wt, thickness = find_per_pipe_weight(weight_df, size, thickness, weight)

        if per_pipe_wt is None:
            st.error("❌ Could not match pipe size/thickness/weight in weight table.")
        else:
            st.write(f"⚖️ Per pipe weight: {per_pipe_wt:.2f} kg (thickness {thickness} mm)")
            available, max_pcs, stock_kg = check_stock(stock_df, size, thickness, per_pipe_wt, qty_required)

            if available is None:
                st.error("❌ Could not find matching stock row.")
            elif available:
                st.success(f"✅ Stock Available! Max {int(max_pcs)} pcs ({stock_kg:.1f} kg) in stock.")
                st.info(f"Your requirement {qty_required} pcs = {qty_required * per_pipe_wt:.1f} kg.")
            else:
                st.warning(f"⚠️ Not enough stock. Only {int(max_pcs)} pcs ({stock_kg:.1f} kg) available.")
                st.info(f"Your requirement {qty_required} pcs = {qty_required * per_pipe_wt:.1f} kg.")



