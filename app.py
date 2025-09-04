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
# Normalize thickness columns
# --------------------------
def normalize_columns(df):
    rename_map = {}
    for col in df.columns:
        try:
            val = float(col)  # if column is numeric-like
            rename_map[col] = str(val).rstrip("0").rstrip(".")  # 1.20 -> "1.2"
        except:
            rename_map[col] = col
    return df.rename(columns=rename_map)

# --------------------------
# Load weight (fixed file)
# --------------------------
@st.cache_data
def load_weight():
    df = pd.read_excel(WEIGHT_FILE)
    df = normalize_columns(df)
    return df

# --------------------------
# Load daily stock (latest file)
# --------------------------
@st.cache_data
def load_stock():
    stock_files = glob.glob(os.path.join(DATA_DIR, "Stocks*.xlsx"))
    if not stock_files:
        st.error(f"❌ No stock file found in `{DATA_DIR}`. Please upload today's file.")
        st.stop()
    latest_file = max(stock_files, key=os.path.getctime)
    stock_df = pd.read_excel(latest_file, header=1)
    stock_df = normalize_columns(stock_df)
    return stock_df, os.path.basename(latest_file)

# --------------------------
# Parse user query
# --------------------------
def parse_query(query):
    query = query.strip().lower().replace("inch", '"').replace("inches", '"')
    parts = query.split()
    size, thickness, weight = None, None, None
    for p in parts:
        if "nb" in p or "od" in p or "x" in p or '"' in p or "mm" in p:
            size = p.replace("mm", "")
        elif "mm" in p:
            thickness = p.replace("mm", "")
        elif "kg" in p:
            weight = p.replace("kg", "")
    return size, thickness, weight

# --------------------------
# Find availability
# --------------------------
def check_availability(size, thickness, weight, qty, stock_df, weight_df):
    # filter weight file row by size
    mask = (
        (weight_df.iloc[:, 0].astype(str).str.lower() == str(size).lower()) |
        (weight_df.iloc[:, 1].astype(str).str.lower() == str(size).lower()) |
        (weight_df.iloc[:, 2].astype(str).str.lower() == str(size).lower())
    )
    row = weight_df[mask]

    if row.empty:
        return None, None, None, "❌ Pipe size not found in weight table."

    row = row.iloc[0]

    # if user gave thickness
    if thickness:
        if thickness not in row.index:
            return None, None, None, f"❌ Thickness {thickness}mm not found for {size}."
        weight_per_pc = row[thickness]
    elif weight:
        # find closest weight match in that row
        numeric_cols = [c for c in row.index if c.replace(".", "").isdigit()]
        vals = row[numeric_cols].astype(float)
        match = vals[abs(vals - float(weight)).idxmin()]
        weight_per_pc = match
        thickness = vals[abs(vals - float(weight)).idxmin()]
    else:
        return None, None, None, "❌ Neither thickness nor weight specified."

    total_weight = weight_per_pc * qty / 1000  # convert kg → MT

    # lookup stock
    stock_mask = stock_df.iloc[:, 0].astype(str).str.lower() == str(size).lower()
    stock_row = stock_df[stock_mask]

    if stock_row.empty:
        return None, None, None, "❌ Size not found in stock file."

    available_mt = stock_row.iloc[0].get(str(thickness), 0)
    available_pcs = (available_mt * 1000) / weight_per_pc  # MT→kg→pcs

    status = "✅ Available" if available_pcs >= qty else "❌ Not enough stock"
    return available_pcs, available_mt, total_weight, status

# --------------------------
# Streamlit UI
# --------------------------
def main():
    st.title("📊 Pipe Stock Availability Checker")

    weight_df = load_weight()
    stock_df, stock_file = load_stock()
    st.success(f"✅ Using stock file: {stock_file}")

    query = st.text_input("Enter pipe (e.g. 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 19.05 OD 1.2mm)")
    qty = st.number_input("Enter required quantity (pcs)", min_value=1, value=10)

    if st.button("Check Availability") and query:
        size, thickness, weight = parse_query(query)
        available_pcs, available_mt, total_weight, status = check_availability(
            size, thickness, weight, qty, stock_df, weight_df
        )

        st.subheader("🔍 Result")
        st.write(f"**Query:** {query}")
        st.write(f"**Required Qty:** {qty} pcs")

        if status.startswith("❌"):
            st.error(status)
        else:
            st.success(status)
            st.write(f"**Available Qty (pcs):** {available_pcs:.0f}")
            st.write(f"**Available Stock (MT):** {available_mt:.2f}")
            st.write(f"**Your Order Weight (MT):** {total_weight:.3f}")

if __name__ == "__main__":
    main()





