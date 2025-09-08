import streamlit as st
import pandas as pd
import os
import re

# ------------------------------
# Helper functions
# ------------------------------
def get_latest_stock_file(folder: str) -> str:
    """Return the latest stock file from data/ folder."""
    files = [f for f in os.listdir(folder) if f.startswith("Stocks(") and f.endswith(".xlsx")]
    if not files:
        return None
    # Sort by date inside filename
    files.sort(key=lambda x: re.findall(r"\d{2}-\d{2}-\d{4}", x)[0], reverse=True)
    return os.path.join(folder, files[0])

def create_weight_sheet(width_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate weight per pipe (kg) for each category and thickness.
    Formula: Mass (kg) = 0.0471 * W * t
    W = width (mm), t = thickness (mm)
    """
    weight_df = width_df.copy()
    thickness_cols = [col for col in weight_df.columns if "1." in col or col.endswith("mm") or col.replace(".","").isdigit()]
    
    for col in thickness_cols:
        t = float(col.replace("Thickness", "").replace("mm", "").strip())
        weight_df[col] = weight_df[col].apply(lambda w: round(0.0471 * w * t, 2) if pd.notnull(w) else None)
    
    return weight_df

def merge_stock_and_weight(stock_df: pd.DataFrame, weight_df: pd.DataFrame) -> pd.DataFrame:
    """Merge stock data (MT) with weight data (kg/pipe) and calculate number of pipes."""
    merged = pd.merge(
        stock_df,
        weight_df,
        left_on="Pipe Category (mm / NB / OD)",
        right_on="Pipe Category in  NB or  OD or mm",
        how="left",
        suffixes=("_Stock", "_Weight")
    )

    thickness_cols = [col for col in stock_df.columns if "mm" in col and "Thickness" in col]

    results = []
    for col in thickness_cols:
        stock_mt = merged[col + "_Stock"] if col + "_Stock" in merged.columns else merged[col]
        weight_kg = merged[col + "_Weight"] if col + "_Weight" in merged.columns else merged[col]
        num_pipes = (stock_mt * 1000 / weight_kg).round(0).replace([float("inf"), -float("inf")], 0)

        temp = merged[["Pipe Category (Inches)", "Pipe Category (mm / NB / OD)"]].copy()
        temp["Thickness"] = col.replace("Thickness", "").replace("mm", "").strip()
        temp["Stock_MT"] = stock_mt
        temp["Weight_kg_per_pipe"] = weight_kg
        temp["No_of_Pipes"] = num_pipes
        results.append(temp)

    return pd.concat(results, ignore_index=True)

# ------------------------------
# Streamlit App
# ------------------------------
st.set_page_config(page_title="Daily Pipe Stock Dashboard", layout="wide")
st.title("📊 Daily Pipe Stock Dashboard")

# Load width (fixed) and create weight sheet
width_file = os.path.join("data", "slit_width.xlsx")
width_df = pd.read_excel(width_file)
weight_df = create_weight_sheet(width_df)

# Load latest stock file
stock_file = get_latest_stock_file("data")
if stock_file is None:
    st.error("❌ No stock file found in data/ folder!")
    st.stop()

stock_df = pd.read_excel(stock_file)

# Merge & calculate
final_df = merge_stock_and_weight(stock_df, weight_df)

# ------------------------------
# Search Filters
# ------------------------------
col1, col2 = st.columns(2)
with col1:
    pipe_search = st.text_input("🔍 Search by Pipe Category (Inches / NB / OD / mm):").strip()
with col2:
    thickness_search = st.selectbox("📏 Select Thickness (mm):", sorted(final_df["Thickness"].unique()))

# Apply filters
filtered_df = final_df.copy()
if pipe_search:
    filtered_df = filtered_df[filtered_df["Pipe Category (mm / NB / OD)"].str.contains(pipe_search, case=False, na=False) |
                              filtered_df["Pipe Category (Inches)"].str.contains(pipe_search, case=False, na=False)]
if thickness_search:
    filtered_df = filtered_df[filtered_df["Thickness"] == thickness_search]

# ------------------------------
# Display results
# ------------------------------
st.subheader("📌 Filtered Results")
st.dataframe(filtered_df, use_container_width=True)

st.markdown("---")
st.success(f"✅ Data loaded from **{os.path.basename(stock_file)}** | Auto-refresh daily at 9 AM")


