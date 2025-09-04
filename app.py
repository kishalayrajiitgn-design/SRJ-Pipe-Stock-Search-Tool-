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
# Helpers
# --------------------------
def normalize_columns(df):
    """Standardize thickness columns to remove .0 endings (e.g. 1.20 -> 1.2)."""
    rename_map = {}
    for col in df.columns:
        try:
            val = float(col)
            rename_map[col] = str(val).rstrip("0").rstrip(".")
        except:
            rename_map[col] = col
    return df.rename(columns=rename_map)

# --------------------------
# Load fixed weight file
# --------------------------
@st.cache_data
def load_weight():
    df = pd.read_excel(WEIGHT_FILE)
    df = normalize_columns(df)
    return df

# --------------------------
# Load latest stock file
# --------------------------
@st.cache_data
def load_stock():
    stock_files = glob.glob(os.path.join(DATA_DIR, "Stocks*.xlsx"))
    if not stock_files:
        st.error(f"❌ No stock file found in `{DATA_DIR}`. Please upload today's file.")
        st.stop()
    latest_file = max(stock_files, key=os.path.getctime)
    df = pd.read_excel(latest_file, header=1)  # stock sheet usually has header offset
    df = normalize_columns(df)
    return df, os.path.basename(latest_file)

# --------------------------
# Parse user query
# --------------------------
def parse_query(query):
    query = query.strip().lower().replace("inch", '"').replace("inches", '"')
    size, thickness, weight = None, None, None
    parts = query.split()
    for p in parts:
        if "nb" in p or "od" in p or "x" in p or '"' in p or "mm" in p:
            size = p.replace("mm", "")
        elif "mm" in p:
            thickness = p.replace("mm", "")
        elif "kg" in p:
            weight = p.replace("kg", "")
    return size, thickness, weight

# --------------------------
# Main matching logic
# --------------------------
def check_availability(size, thickness, weight, qty, stock_df, weight_df):
    # --- Find matching row in weight table ---
    mask = (
        (weight_df.iloc[:, 0].astype(str).str.lower() == str(size).lower()) |
        (weight_df.iloc[:, 1].astype(str).str.lower() == str(size).lower()) |
        (weight_df.iloc[:, 2].astype(str).str.lower() == str(size).lower())
    )
    row = weight_df[mask]
    if row.empty:
        return None, None, None, "❌ Pipe size not found in weight table."
    row = row.iloc[0]

    # --- Determine weight per pipe ---
    if thickness:
        if thickness not in row.index:
            return None, None, None, f"❌ Thickness {thickness}mm not found for {size}."
        weight_per_pc = row[thickness]
    elif weight:
        numeric_cols = [c for c in row.index if c.replace(".", "").isdigit()]
        vals = row[numeric_cols].astype(float)
        closest = vals[abs(vals - float(weight)).idxmin()]
        weight_per_pc = closest
        thickness = abs(vals - float(weight)).idxmin()
    else:
        return None, None, None, "❌ Neither thickness nor weight specified."

    total_weight_kg = weight_per_pc * qty
    total_weight_mt = total_weight_kg / 1000

    # --- Lookup in stock file ---
    stock_mask = stock_df.iloc[:, 1].astype(str).str.lower() == str(size).lower()
    stock_row = stock_df[stock_mask]
    if stock_row.empty:
        return None, None, None, "❌ Size not found in stock file."

    available_mt = stock_row.iloc[0].get(str(thickness), 0)
    available_pcs = (available_mt * 1000) / weight_per_pc

    if available_pcs >= qty:
        status = "✅ Available"
    else:
        status = "❌ Not enough stock"

    return available_pcs, available_mt, (total_weight_kg, total_weight_mt), status

# --------------------------
# Streamlit UI
# --------------------------
def main():
    st.title("📊 Pipe Stock Availability Checker")

    weight_df = load_weight()
    stock_df, stock_file = load_stock()
    st.success(f"✅ Using stock file: {stock_file}")

    query = st.text_input("Enter pipe (e.g. 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 0.75\" 1.2mm)")
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
            st.write(f"**Your Order Weight:** {total_weight[0]:.2f} kg ({total_weight[1]:.3f} MT)")

if __name__ == "__main__":
    main()







