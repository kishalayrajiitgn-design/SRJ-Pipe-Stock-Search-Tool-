# app.py
import streamlit as st
import pandas as pd
import numpy as np
import glob
import re
from pathlib import Path

DATA_DIR = Path("data")
LENGTH_M = 6.0
DENSITY_MS = 7850.0  # kg/m3 (not used explicitly because we use 0.0471 factor)
# Precomputed factor for length=6m and density=7850: mass(kg) = 0.0471 * W(mm) * t(mm)
MASS_FACTOR = 0.0471

st.set_page_config(page_title="Pipe Search & Availability", layout="wide")

@st.cache_data(ttl=300)
def find_latest_stocks_file():
    files = sorted(DATA_DIR.glob("Stocks*.xlsx"), key=lambda p: p.name, reverse=True)
    return files[0] if files else None

@st.cache_data(ttl=300)
def load_widths():
    """Load widths excel and produce long dataframe: category -> thickness -> width_mm"""
    p = DATA_DIR / "width.xlsx"
    if not p.exists():
        st.warning(f"width.xlsx not found at {p}")
        return pd.DataFrame()
    df = pd.read_excel(p, engine="openpyxl")
    # normalize header names by stripping whitespace
    df.columns = [str(c).strip() for c in df.columns]
    # melt thickness columns to long format
    # find thickness columns (look for numeric in header)
    thresh_cols = [c for c in df.columns if re.search(r"1\.2|1\.4|1\.6|1\.8|2\.0|2\.2|2\.5|2\.9|3\.2|3\.6|4\.0|4\.5|5\.0|5\.5|6\.0|6\.5|7\.0", str(c))]
    if not thresh_cols:
        # attempt to use all columns except first as thicknesss
        thresh_cols = df.columns[1:].tolist()
    id_col = df.columns[0]
    df_long = df.melt(id_vars=[id_col], value_vars=thresh_cols, var_name="thickness_col", value_name="width_mm")
    df_long['thickness_mm'] = df_long['thickness_col'].astype(str).str.extract(r"(\d+\.?\d*)").astype(float)
    df_long = df_long.rename(columns={id_col: "category"})
    df_long['category'] = df_long['category'].astype(str).str.strip()
    df_long = df_long.dropna(subset=['width_mm']).reset_index(drop=True)
    return df_long[['category','thickness_mm','width_mm']]

@st.cache_data(ttl=300)
def load_stocks():
    p = find_latest_stocks_file()
    if p is None:
        st.warning("No Stocks file found in data/. Upload Stocks(DD-MM-YYYY).xlsx")
        return pd.DataFrame()
    df = pd.read_excel(p, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    # standardize names
    # find thickness columns similarly to width
    id_cols = [c for c in df.columns if not re.search(r"1\.2|1\.4|1\.6|1\.8|2\.0|2\.2|2\.5|2\.9|3\.2|3\.6|4\.0|4\.5|5\.0|5\.5|6\.0|6\.5|7\.0", str(c))]
    thickness_cols = [c for c in df.columns if c not in id_cols]
    if len(id_cols) >= 2:
        # assume first two are Pipe Category columns
        id_col = id_cols[0]  # should be Pipe Category (Inches)
        id_col2 = id_cols[1] # Pipe Category (mm / NB / OD)
    else:
        # fallback
        id_col = df.columns[0]
        id_col2 = df.columns[1] if len(df.columns)>1 else None

    df_long = df.melt(id_vars=[id_col, id_col2] if id_col2 else [id_col],
                      value_vars=thickness_cols,
                      var_name='thickness_col',
                      value_name='stock_value')
    df_long['thickness_mm'] = df_long['thickness_col'].astype(str).str.extract(r"(\d+\.?\d*)").astype(float)
    df_long = df_long.rename(columns={id_col: 'category_inch', id_col2: 'category_mm'})
    df_long['category_inch'] = df_long['category_inch'].astype(str).str.strip()
    df_long['category_mm'] = df_long['category_mm'].astype(str).str.strip() if id_col2 else ""
    df_long = df_long.dropna(subset=['stock_value']).reset_index(drop=True)
    return df_long[['category_inch','category_mm','thickness_mm','stock_value']]

# Helper utilities
def find_width_for(category_query, thickness_query, widths_df, tol_choose_nearest=True):
    """Try to find a width (mm) for a given category and thickness.
       category_query: string to match (search in category column)
       thickness_query: numeric (mm)
    """
    # exact category match (case-insensitive contains)
    df_cat = widths_df[widths_df['category'].str.lower().str.contains(category_query.lower())]
    if df_cat.empty:
        # fallback to partial tokens: try split tokens and search one by one
        for token in re.split(r'[\s,\/xX"]+', category_query):
            token = token.strip()
            if not token:
                continue
            df_cat = widths_df[widths_df['category'].str.lower().str.contains(token.lower())]
            if not df_cat.empty:
                break
    if df_cat.empty:
        return None, "category_not_found"

    # find thickness match
    if thickness_query is not None:
        # exact
        exact = df_cat[np.isclose(df_cat['thickness_mm'], thickness_query)]
        if not exact.empty:
            w = exact.iloc[0]['width_mm']
            return float(w), f"matched_exact_thickness_{thickness_query}"
        else:
            if tol_choose_nearest:
                df_cat = df_cat.copy().dropna(subset=['thickness_mm'])
                df_cat['absdiff'] = (df_cat['thickness_mm'] - thickness_query).abs()
                best = df_cat.sort_values('absdiff').iloc[0]
                return float(best['width_mm']), f"matched_nearest_thickness_{best['thickness_mm']}"
            else:
                return None, "thickness_not_found"
    else:
        # if no thickness provided, pick the thinnest available
        best = df_cat.sort_values('thickness_mm').iloc[0]
        return float(best['width_mm']), f"matched_no_thickness_picked_{best['thickness_mm']}"

def compute_mass_per_item(width_mm, thickness_mm):
    """Mass in kg for one pipe of length 6 m"""
    return MASS_FACTOR * width_mm * thickness_mm

def parse_user_query(qtext):
    """Attempt to parse user free text queries into structured tokens:
       return dict with keys: category_token, thickness_mm (float or None), weight_per_item_kg (float or None), qty (int or None)
       Support examples:
         '2x2,18kg' -> category '2x2', weight 18 kg
         '40x40 12kg' -> category '40x40', weight 12
         '20x20 1.6mm' -> category '20x20', thickness 1.6
         '1\" 18kg' -> category 1"
    """
    q = qtext.strip()
    result = {'raw': q, 'category': None, 'thickness_mm': None, 'weight_kg': None, 'qty': None}
    # Quantity may be provided separately; user will usually send qty input field. But try find trailing numbers
    # Find weight in kg
    m_w = re.search(r'(\d+(\.\d+)?)\s*kg\b', q, flags=re.IGNORECASE)
    if m_w:
        result['weight_kg'] = float(m_w.group(1))
        q = q.replace(m_w.group(0), ' ')
    # Find thickness in mm
    m_t = re.search(r'(\d+(\.\d+)?)\s*mm\b', q, flags=re.IGNORECASE)
    if m_t:
        result['thickness_mm'] = float(m_t.group(1))
        q = q.replace(m_t.group(0), ' ')
    # find inches notation like 1/2" or 1.5"
    m_in = re.search(r'(\d+(\.\d+)?)(\s*["”])', q)
    if m_in:
        result['category'] = m_in.group(0).strip()
        q = q.replace(m_in.group(0), ' ')
    # if still nothing, try token like 40x40 or 20NB etc.
    if not result['category']:
        m_cat = re.search(r'([0-9]+(?:\.[0-9]+)?[xX]\s*[0-9]+(?:\.[0-9]+)?)', q)
        if m_cat:
            result['category'] = m_cat.group(1).replace(' ', '')
            q = q.replace(m_cat.group(0), ' ')
    # try NB or OD tokens
    if not result['category']:
        m_nb = re.search(r'(\d+(?:\.\d+)?\s*(NB|nb|OD|od))', q)
        if m_nb:
            result['category'] = m_nb.group(1).strip()
            q = q.replace(m_nb.group(0), ' ')
    # if still not found, take the remaining non-numeric tokens
    if not result['category']:
        remainder = re.sub(r'[\d\.\,\-\s]+',' ', q).strip()
        if remainder:
            result['category'] = remainder
    # final fallback raw
    if not result['category']:
        result['category'] = result['raw']
    return result

# UI
st.title("Pipe Search, Weight & Availability — (6 m fixed length)")
st.markdown("Upload daily `Stocks(DD-MM-YYYY).xlsx` into data/ and keep `width.xlsx` in data/. Click **Refresh data** after you update files in GitHub.")

col1, col2 = st.columns([2,1])
with col2:
    st.subheader("Assumptions / Settings")
    STOCKS_UNIT = st.selectbox("Stocks file units (how 'stock_value' column should be interpreted):",
                               options=["MT (metric ton)", "kg", "pcs"], index=0,
                               help="If Stocks file values are in metric tons choose MT. If they are counts choose pcs.")
    tol_nearest = st.checkbox("Pick nearest thickness if exact thickness not present", value=True)
    reload = st.button("Refresh data (re-read Excel files)")

if reload:
    # clear cache of loaders
    load_widths.clear()
    load_stocks.clear()
    st.experimental_rerun()

widths_df = load_widths()
stocks_df = load_stocks()

if widths_df.empty:
    st.error("Widths data not loaded. Put `width.xlsx` in data/ and ensure it has thickness columns.")
    st.stop()
if stocks_df.empty:
    st.warning("Stocks data not loaded or is empty. Upload Stocks file into data/ and press 'Refresh data'.")

# Search area
st.subheader("Search (flexible input)")
query = st.text_input("Enter pipe search (examples: '2x2,18kg', '40x40 12kg', '20x20 1.6mm', '1\" 18kg', '25 NB 3kg')", value="")
qty = st.number_input("Quantity required (number of pieces)", min_value=1, value=1, step=1)
st.write("You can supply thickness in the search (e.g. '20x20 1.6mm') or leave thickness blank and select below.")
manual_thickness = st.text_input("Optional: Enter thickness (mm) to override parsed thickness (leave blank to use parsed)", value="")
if manual_thickness.strip():
    try:
        manual_thickness_val = float(manual_thickness)
    except:
        st.error("Invalid manual thickness. Leave blank or enter a number like 1.6")
        manual_thickness_val = None
else:
    manual_thickness_val = None

if st.button("Search"):
    if not query.strip():
        st.warning("Please enter a search query.")
    else:
        parsed = parse_user_query(query)
        if manual_thickness_val is not None:
            parsed['thickness_mm'] = manual_thickness_val

        st.write("Parsed query:", parsed)

        # find width
        width_mm, match_status = find_width_for(parsed['category'], parsed['thickness_mm'], widths_df, tol_choose_nearest=tol_nearest)
        if width_mm is None:
            st.error(f"Could not find width for category '{parsed['category']}'. Try other spelling or check width.xlsx.")
        else:
            chosen_thickness = parsed['thickness_mm']
            # if parsed weight given by user, use it; else compute using width & thickness
            if parsed['weight_kg'] is not None:
                mass_per_item = parsed['weight_kg']
                computed_note = f"Using user-provided weight {mass_per_item} kg"
            else:
                if parsed['thickness_mm'] is None:
                    st.info("No thickness provided: picking a default thickness from widths table match.")
                    # match_status likely contains chosen thickness
                mass_per_item = compute_mass_per_item(width_mm, parsed['thickness_mm'] if parsed['thickness_mm'] else widths_df[widths_df['category'].str.lower().str.contains(parsed['category'].lower())].sort_values('thickness_mm').iloc[0]['thickness_mm'])
                computed_note = f"Computed using width={width_mm} mm and thickness={parsed['thickness_mm']} mm (match: {match_status})"

            total_weight = mass_per_item * qty

            st.metric(label="Mass per item (kg)", value=f"{mass_per_item:.4f}")
            st.metric(label=f"Total mass for qty={qty} (kg)", value=f"{total_weight:.4f}")
            st.write("Match info:", match_status)
            st.write(computed_note)

            # Now check stocks availability from stocks_df
            if not stocks_df.empty:
                # find stock row(s) matching category
                cat = parsed['category']
                # try match in category_inch or category_mm
                srows = stocks_df[stocks_df['category_inch'].str.lower().str.contains(cat.lower(), na=False) | stocks_df['category_mm'].str.lower().str.contains(cat.lower(), na=False)]
                if srows.empty:
                    # try token fallback
                    for token in re.split(r'[\s,\/xX"]+', cat):
                        if not token:
                            continue
                        srows = stocks_df[stocks_df['category_inch'].str.lower().str.contains(token.lower(), na=False) | stocks_df['category_mm'].str.lower().str.contains(token.lower(), na=False)]
                        if not srows.empty:
                            break
                if srows.empty:
                    st.warning("No matching rows in Stocks file for this category. Cannot check availability.")
                else:
                    # sum stock values across matching rows for the exact thickness column
                    desired_th = parsed['thickness_mm']
                    if desired_th is None:
                        # choose nearest thickness from stocks_df
                        srows['absdiff'] = (srows['thickness_mm'] - (widths_df['thickness_mm'].min() if widths_df['thickness_mm'].notnull().any() else 0)).abs()
                        chosen_stock_rows = srows
                    else:
                        # find exact thickness rows or nearest
                        exact = srows[np.isclose(srows['thickness_mm'], desired_th)]
                        if not exact.empty:
                            chosen_stock_rows = exact
                        else:
                            srows['absdiff'] = (srows['thickness_mm'] - desired_th).abs()
                            chosen_stock_rows = srows.sort_values('absdiff').iloc[[0]]

                    stock_sum = chosen_stock_rows['stock_value'].sum()
                    # convert stock_sum based on selected unit
                    if STOCKS_UNIT.startswith("MT"):
                        stock_kg = float(stock_sum) * 1000.0
                    elif STOCKS_UNIT == "kg":
                        stock_kg = float(stock_sum)
                    else:  # pcs
                        stock_kg = None

                    if stock_kg is None:
                        # stock units are pieces, compare counts
                        stock_pcs = float(stock_sum)
                        avail = stock_pcs >= qty
                        st.write(f"Stock (pieces) for matched rows: {stock_pcs:.2f}")
                        st.write(f"Requested qty {qty} pieces -> Available: {'Yes' if avail else 'No'}")
                        if avail:
                            st.write(f"Remaining pieces after order: {stock_pcs - qty:.2f}")
                    else:
                        # we have stock in kg
                        avail = stock_kg >= total_weight
                        st.write(f"Stock (kg) for matched rows: {stock_kg:.3f} kg")
                        st.write(f"Requested total weight: {total_weight:.3f} kg -> Available: {'Yes' if avail else 'No'}")
                        if avail:
                            st.write(f"Remaining stock after order: {stock_kg - total_weight:.3f} kg")

            # Show helpful table with width entries for the category
            st.subheader("Widths lookup (matching rows)")
            wmatch = widths_df[widths_df['category'].str.lower().str.contains(parsed['category'].lower(), na=False)]
            if wmatch.empty:
                # try token fallback
                for token in re.split(r'[\s,\/xX"]+', parsed['category']):
                    if not token:
                        continue
                    wmatch = widths_df[widths_df['category'].str.lower().str.contains(token.lower(), na=False)]
                    if not wmatch.empty:
                        break
            if wmatch.empty:
                st.write("No matching width rows found.")
            else:
                st.dataframe(wmatch.sort_values('thickness_mm').reset_index(drop=True))

st.markdown("---")
st.caption("If anything doesn't match your expectation (units/stock type), change 'Stocks file units' or update width.xlsx/Stocks file columns. Contact dev for further customization.")

