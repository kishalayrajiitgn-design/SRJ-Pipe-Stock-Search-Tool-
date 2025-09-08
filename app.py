# app.py
import streamlit as st
import pandas as pd
import glob
import os
import re
from datetime import datetime

st.set_page_config(page_title="SRJ Peety Steels Private Limited Pipe Stock Search Tool", layout="wide")

DATA_FOLDER = "data"
PIPE_MASS_FILE = os.path.join(DATA_FOLDER, "pipe_mass.xlsx")  # fixed file

# -------------------------
# Helpers
# -------------------------
def find_latest_stock_file(pattern="Stocks(*).xlsx"):
    files = glob.glob(os.path.join(DATA_FOLDER, "Stocks(*).xlsx"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def find_col_by_substring(df, substr_list):
    """Return first column name that contains any substring in substr_list (case-insensitive)."""
    cols = list(df.columns)
    for s in substr_list:
        for c in cols:
            if s.lower() in str(c).lower():
                return c
    return None

def safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def parse_free_text(text):
    """
    Try to extract: category string, weight_kg, thickness_mm from a free-text input like:
      "40x40 12kg", "20x20 1.6mm", "2x2,18kg", "100x100 5"
    Returns dict with possible keys.
    """
    out = {"category": None, "weight_kg": None, "thickness_mm": None}
    if not text or not str(text).strip():
        return out
    s = text.lower()
    # remove commas
    s = s.replace(",", " ")
    # extract weight like '12kg' or '12 kg' or standalone number with kg assumption later
    m = re.search(r'([\d.]+)\s*kg', s)
    if m:
        out["weight_kg"] = safe_float(m.group(1))
        s = re.sub(m.group(0), " ", s)
    else:
        # maybe number followed by mm
        m2 = re.search(r'([\d.]+)\s*mm', s)
        if m2:
            out["thickness_mm"] = safe_float(m2.group(1))
            s = re.sub(m2.group(0), " ", s)
        else:
            # maybe a bare weight number present (ambiguous) - don't assume
            pass

    # Try to find 'X' or 'x' size patterns like 100x100, 2x2
    m3 = re.search(r'(\d+\.?\d*)\s*[xX]\s*(\d+\.?\d*)', s)
    if m3:
        out["category"] = f"{m3.group(1)}x{m3.group(2)}"
        # remove it
        s = re.sub(m3.group(0), " ", s)
    else:
        # fallback: first token that's not weight or mm
        tokens = [t for t in re.split(r'\s+', s) if t.strip()]
        for t in tokens:
            if re.match(r'^[\d\.]+(kg|mm)$', t):
                continue
            out["category"] = t
            break
    return out

def availability_label(row, qty_required):
    try:
        no_of_pipes = float(row.get("No_of_Pipes_in_Stock", 0))
    except Exception:
        no_of_pipes = 0
    if no_of_pipes >= qty_required:
        return "✅ Available"
    if 0 < no_of_pipes < qty_required:
        return "⚠️ Low Stock"
    return "❌ Not Available"

def style_rows(df):
    def _color(row):
        status = row.get("Availability_Status", "")
        if status == "✅ Available":
            return ['background-color: #d4edda']*len(row)
        if status == "⚠️ Low Stock":
            return ['background-color: #fff3cd']*len(row)
        return ['background-color: #f8d7da']*len(row)
    return df.style.apply(_color, axis=1)

# -------------------------
# Load data safely
# -------------------------
st.title("📊 Pipe Stock Search Tool")
st.markdown("Automated daily stock → pipe search. `pipe_mass.xlsx` (fixed) & latest `Stocks(...).xlsx` from `data/` folder.")

if not os.path.exists(PIPE_MASS_FILE):
    st.error(f"Missing fixed file: `{PIPE_MASS_FILE}`. Upload `pipe_mass.xlsx` to the data folder.")
    st.stop()

latest_stock = find_latest_stock_file()
if not latest_stock:
    st.error(f"No stock file found in `{DATA_FOLDER}`. Upload one like `Stocks(DD-MM-YYYY).xlsx`.")
    st.stop()

# Read files
try:
    df_mass = pd.read_excel(PIPE_MASS_FILE)
except Exception as e:
    st.error(f"Error reading pipe mass file: {e}")
    st.stop()

try:
    df_stock = pd.read_excel(latest_stock)
except Exception as e:
    st.error(f"Error reading latest stock file `{os.path.basename(latest_stock)}`: {e}")
    st.stop()

# Normalize column whitespace
df_mass.columns = df_mass.columns.astype(str).str.strip()
df_stock.columns = df_stock.columns.astype(str).str.strip()

# -------------------------
# Identify column names (robust)
# -------------------------
mass_cat_col = df_mass.columns[0]  # first column expected to be category
# thickness columns in mass: all except first
mass_thickness_cols = [c for c in df_mass.columns[1:]]

stock_inch_col = find_col_by_substring(df_stock, ["pipe category (inches)", "pipe category (inch)"]) or df_stock.columns[0]
stock_cat_col = find_col_by_substring(df_stock, ["pipe category (mm", "pipe category (mm /", "pipe category (mm / nb", "pipe category (mm / nb / od)"]) or df_stock.columns[1]
# thickness columns in stock are from 3rd onward (but do robust)
stock_thickness_cols = list(df_stock.columns[2:])

# -------------------------
# Melt mass -> long
# -------------------------
df_mass_long = df_mass.melt(
    id_vars=[mass_cat_col],
    value_vars=mass_thickness_cols,
    var_name="Thickness_mm",
    value_name="Mass_kg"
)

# normalize thickness column values: extract numeric
df_mass_long["Thickness_mm"] = df_mass_long["Thickness_mm"].astype(str).str.extract(r'([\d.]+)', expand=False)
df_mass_long["Thickness_mm"] = pd.to_numeric(df_mass_long["Thickness_mm"], errors='coerce')
df_mass_long["Mass_kg"] = pd.to_numeric(df_mass_long["Mass_kg"], errors='coerce')

# unify category column name to a common name for merge
df_mass_long = df_mass_long.rename(columns={mass_cat_col: "Pipe Category (mm / NB / OD)"})

# -------------------------
# Melt stock -> long
# -------------------------
df_stock_long = df_stock.melt(
    id_vars=[stock_inch_col, stock_cat_col],
    value_vars=stock_thickness_cols,
    var_name="Thickness_mm",
    value_name="Stock_MT"
)

df_stock_long["Thickness_mm"] = df_stock_long["Thickness_mm"].astype(str).str.extract(r'([\d.]+)', expand=False)
df_stock_long["Thickness_mm"] = pd.to_numeric(df_stock_long["Thickness_mm"], errors='coerce')
df_stock_long["Stock_MT"] = pd.to_numeric(df_stock_long["Stock_MT"], errors='coerce').fillna(0)

# normalize column names
df_stock_long = df_stock_long.rename(columns={stock_inch_col: "Pipe Category (Inches)", stock_cat_col: "Pipe Category (mm / NB / OD)"})

# -------------------------
# Merge mass with stock
# -------------------------
df = pd.merge(
    df_stock_long,
    df_mass_long,
    on=["Pipe Category (mm / NB / OD)", "Thickness_mm"],
    how="left"
)

# -------------------------
# UI: Filters
# -------------------------
st.sidebar.header("Search Filters")
pipe_category_input = st.sidebar.text_input("Pipe Category (inch/mm/NB/OD) — free text or exact e.g. 100x100 or 4\" or 50 NB")
free_text_input = st.sidebar.text_input("Free text (eg. '40x40 12kg' or '20x20 1.6mm') — optional")
thickness_input = st.sidebar.text_input("Thickness (mm) or range like 1.2-2.5 (optional)")
weight_input = st.sidebar.text_input("Weight (kg) - exact or approximate (optional)")
quantity_required = st.sidebar.number_input("Quantity required (pieces)", min_value=1, value=1, step=1)

st.sidebar.markdown("---")
if st.sidebar.button("Clear filters"):
    st.experimental_rerun()

# parse free text if provided
parsed = parse_free_text(free_text_input)
if parsed["category"] and not pipe_category_input:
    pipe_category_input = parsed["category"]
if parsed["weight_kg"] and not weight_input:
    weight_input = str(parsed["weight_kg"])
if parsed["thickness_mm"] and not thickness_input:
    thickness_input = str(parsed["thickness_mm"])

# -------------------------
# Apply filters progressively
# -------------------------
df_filtered = df.copy()

# Pipe category match (ignore spaces/case)
if pipe_category_input and str(pipe_category_input).strip():
    search = str(pipe_category_input).strip().lower().replace(" ", "")
    mask_inch = df_filtered["Pipe Category (Inches)"].astype(str).str.lower().str.replace(" ", "").str.contains(search, na=False)
    mask_mmnb = df_filtered["Pipe Category (mm / NB / OD)"].astype(str).str.lower().str.replace(" ", "").str.contains(search, na=False)
    df_filtered = df_filtered[mask_inch | mask_mmnb]

# Thickness filter
if thickness_input and str(thickness_input).strip():
    try:
        t_input = str(thickness_input).strip()
        if "-" in t_input:
            parts = [p.strip() for p in t_input.split("-")]
            tmin = float(parts[0]); tmax = float(parts[1])
            df_filtered = df_filtered[(df_filtered["Thickness_mm"] >= tmin) & (df_filtered["Thickness_mm"] <= tmax)]
        else:
            tval = float(t_input)
            df_filtered = df_filtered[df_filtered["Thickness_mm"] == tval]
    except Exception:
        st.sidebar.warning("Thickness input invalid. Use single value like `1.6` or range `1.2-2.5`.")

# Weight filter (approximate match allowed)
if weight_input and str(weight_input).strip():
    try:
        wval = float(re.findall(r'[\d.]+', str(weight_input))[0])
        # tolerance ±0.5 kg
        tol = 0.5
        df_filtered = df_filtered[(df_filtered["Mass_kg"].notna()) & ((df_filtered["Mass_kg"] - wval).abs() <= tol)]
    except Exception:
        st.sidebar.warning("Weight input invalid. Enter numeric (e.g. 12 or 12.5).")

# -------------------------
# Calculations & availability
# -------------------------
# Mass_kg may be NaN — treat as not available / N/A
df_filtered["Mass_kg"] = pd.to_numeric(df_filtered["Mass_kg"], errors="coerce")
df_filtered["Stock_MT"] = pd.to_numeric(df_filtered["Stock_MT"], errors="coerce").fillna(0)

# No_of_Pipes_in_Stock: avoid division by zero and NaN mass
def calc_no_pipes(row):
    mass = row["Mass_kg"]
    stock = row["Stock_MT"]
    if pd.isna(mass) or mass == 0:
        return 0.0
    return (stock * 1000.0) / mass

df_filtered["No_of_Pipes_in_Stock"] = df_filtered.apply(calc_no_pipes, axis=1)
df_filtered["No_of_Pipes_in_Stock"] = df_filtered["No_of_Pipes_in_Stock"].fillna(0).round(0).astype(int)

df_filtered["Total_Weight_in_Stock_kg"] = df_filtered["No_of_Pipes_in_Stock"] * df_filtered["Mass_kg"].fillna(0)
df_filtered["Total_Weight_Required_kg"] = df_filtered["Mass_kg"].fillna(0) * quantity_required

df_filtered["Availability_Status"] = df_filtered.apply(lambda r: availability_label(r, quantity_required), axis=1)

# Create display table
display_cols = [
    "Pipe Category (Inches)",
    "Pipe Category (mm / NB / OD)",
    "Thickness_mm",
    "Mass_kg",
    "Stock_MT",
    "No_of_Pipes_in_Stock",
    "Total_Weight_in_Stock_kg",
    "Total_Weight_Required_kg",
    "Availability_Status"
]
display_df = df_filtered[display_cols].copy()

# Format nicely
display_df = display_df.rename(columns={
    "Pipe Category (Inches)": "Category (inches)",
    "Pipe Category (mm / NB / OD)": "Category (mm/NB/OD)",
    "Thickness_mm": "Thickness (mm)",
    "Mass_kg": "Mass per pipe (kg)",
    "Stock_MT": "Stock (MT)",
    "No_of_Pipes_in_Stock": "No. of Pipes in Stock",
    "Total_Weight_in_Stock_kg": "Total Stock Weight (kg)",
    "Total_Weight_Required_kg": "Required Weight (kg)",
    "Availability_Status": "Availability"
})

# -------------------------
# Show UI
# -------------------------
left, right = st.columns([3, 1])

with left:
    st.subheader("🔹 Search Results")
    if display_df.empty:
        st.warning("No matching results. Try fewer filters or check spelling/format.")
    else:
        # Highlight rows by availability
        styled = style_rows(display_df)
        st.dataframe(styled, height=600)

with right:
    st.subheader("Filters summary")
    st.write(f"Latest stock file: **{os.path.basename(latest_stock)}**")
    st.write("**Category filter:**", pipe_category_input or "—")
    st.write("**Free-text parsed:**", free_text_input or "—")
    st.write("**Thickness:**", thickness_input or "—")
    st.write("**Weight:**", weight_input or "—")
    st.write("**Quantity required:**", quantity_required)
    st.markdown("---")
    st.write("Legend:")
    st.write("✅ **Available** — enough pieces in stock")
    st.write("⚠️ **Low Stock** — some pieces, but less than requested")
    st.write("❌ **Not Available** — zero pieces")
    st.markdown("---")
    # quick stats
    total_items = len(display_df)
    total_available = (display_df["Availability"] == "✅ Available").sum()
    st.write("Matching rows:", total_items)
    st.write("Fully available:", total_available)

# -------------------------
# Allow download of filtered results (if any)
# -------------------------
if not display_df.empty:
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Download search results (CSV)", data=csv, file_name="pipe_stock_search_results.csv", mime="text/csv")

# Footer / notes
st.markdown("---")
st.caption("Notes: Mass per pipe missing → treated as N/A and considered not available for quantity calculations. "
           "Weight filter uses ±0.5 kg tolerance. Free-text parsing tries to extract size, weight(kg) or thickness(mm).")

