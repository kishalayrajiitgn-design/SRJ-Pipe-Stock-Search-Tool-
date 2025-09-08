# app.py
import streamlit as st
import pandas as pd
import re
import io
from pathlib import Path
import math

st.set_page_config(page_title="Pipe Stock & Weight", layout="wide")

DATA_DIR = Path("data")
WIDTH_FILE = DATA_DIR / "width.xlsx"
WEIGHT_FILE = DATA_DIR / "weight_sheet.xlsx"
# STOCK files named like Stocks(30-08-2025).xlsx - we'll pick latest by name sort
STOCK_GLOB = "Stocks*.xlsx"

# Constants
MASS_FACTOR = 0.0471  # mass(kg) = 0.0471 * W(mm) * t(mm)
LENGTH_M = 6.0
DENSITY = 7850.0  # for reference (not used directly because of MASS_FACTOR)

# -------------------------
# Utilities
# -------------------------
@st.cache_data(ttl=300)
def find_latest_stock_file():
    files = sorted(DATA_DIR.glob(STOCK_GLOB), key=lambda p: p.name, reverse=True)
    return files[0] if files else None

def normalize_columns(cols):
    """Return normalized column names and mapping original->normalized"""
    mapping = {}
    normalized = []
    for c in cols:
        orig = str(c)
        s = orig.strip()
        # Collapse spaces, lower
        s2 = re.sub(r"\s+", " ", s).strip()
        normalized.append(s2)
        mapping[orig] = s2
    return normalized, mapping

def extract_thickness_from_header(header):
    """Try to get numeric thickness (mm) from a header string using regex"""
    if header is None:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm", header, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    # sometimes header is just like "1.2" or "1.20"
    m2 = re.search(r"^(\d+(?:\.\d+)?)$", header.strip())
    if m2:
        return float(m2.group(1))
    return None

# -------------------------
# Step A: create weight sheet from width.xlsx
# -------------------------
@st.cache_data(ttl=300)
def build_weight_sheet():
    if not WIDTH_FILE.exists():
        return None, "width.xlsx not found in data/"

    df = pd.read_excel(WIDTH_FILE, engine="openpyxl")
    # Normalize column names
    normalized, mapping = normalize_columns(df.columns)
    df.columns = normalized

    # Identify category column (first column)
    category_col = df.columns[0]

    # Identify thickness columns: any column except the first where thickness can be extracted
    thickness_cols = []
    thickness_map = {}  # colname -> thickness
    for c in df.columns[1:]:
        t = extract_thickness_from_header(c)
        if t is None:
            # try to extract number anywhere in header
            m = re.search(r"(\d+(?:\.\d+)?)", c)
            if m:
                try:
                    t = float(m.group(1))
                except:
                    t = None
        if t is not None:
            thickness_cols.append(c)
            thickness_map[c] = t
        else:
            # still include column (but will be ignored)
            pass

    # Melt to long format
    df_long = df.melt(id_vars=[category_col], value_vars=thickness_cols,
                      var_name="thickness_col", value_name="strip_width_mm")
    df_long = df_long.rename(columns={category_col: "pipe_category"})
    # parse thickness numeric
    df_long["thickness_mm"] = df_long["thickness_col"].map(lambda h: thickness_map.get(h, extract_thickness_from_header(h)))
    # drop rows with no width
    df_long = df_long.dropna(subset=["strip_width_mm", "thickness_mm"]).copy()
    # ensure numeric
    df_long["strip_width_mm"] = pd.to_numeric(df_long["strip_width_mm"], errors="coerce")
    df_long = df_long.dropna(subset=["strip_width_mm"])

    # compute mass
    df_long["mass_kg"] = (MASS_FACTOR * df_long["strip_width_mm"] * df_long["thickness_mm"]).round(6)

    # keep columns of interest
    weight_sheet = df_long[["pipe_category", "thickness_mm", "strip_width_mm", "mass_kg"]].reset_index(drop=True)
    # Save to data/weight_sheet.xlsx
    weight_sheet.to_excel(WEIGHT_FILE, index=False, engine="openpyxl")
    return weight_sheet, None

# -------------------------
# Step B: load stocks and merge with weight sheet
# -------------------------
@st.cache_data(ttl=300)
def load_and_merge_stock_with_weight():
    # find latest stock file
    stock_file = find_latest_stock_file()
    if stock_file is None:
        return None, "No Stocks file found in data/ (expected Stocks*.xlsx)"
    # read stocks
    s = pd.read_excel(stock_file, engine="openpyxl")
    # normalize columns
    norm_cols, mapping = normalize_columns(s.columns)
    s.columns = norm_cols

    # identify category columns; we expect two identifier columns (like Pipe Category (Inches), Pipe Category (mm / NB / OD))
    # fallback: first two columns
    id_cols = s.columns[:2].tolist()
    # identify thickness columns (remaining columns)
    thickness_cols = s.columns[2:].tolist()
    # map thickness column names to numeric thickness
    thickness_map = {}
    valid_cols = []
    for c in thickness_cols:
        t = extract_thickness_from_header(c)
        if t is None:
            # try find a number in the header
            m = re.search(r"(\d+(?:\.\d+)?)", c)
            if m:
                try:
                    t = float(m.group(1))
                except:
                    t = None
        if t is not None:
            thickness_map[c] = t
            valid_cols.append(c)
    if not valid_cols:
        return None, f"No thickness-like columns found in Stocks file: {stock_file.name}"

    # melt stocks to long form: one row per category & thickness
    s_long = s.melt(id_vars=id_cols, value_vars=valid_cols, var_name="thickness_col", value_name="stock_mt")
    # unify category by combining inch and mm identifiers into single search key
    def unify_cat(row):
        a = str(row[id_cols[0]]) if pd.notna(row[id_cols[0]]) else ""
        b = str(row[id_cols[1]]) if len(id_cols)>1 and pd.notna(row[id_cols[1]]) else ""
        # prefer non-empty
        key = a if a.strip() else b
        # also include combined
        return key.strip()
    s_long["pipe_category"] = s_long.apply(unify_cat, axis=1)
    s_long["thickness_mm"] = s_long["thickness_col"].map(thickness_map)
    s_long = s_long.dropna(subset=["stock_mt", "thickness_mm", "pipe_category"])
    # ensure numeric
    s_long["stock_mt"] = pd.to_numeric(s_long["stock_mt"], errors="coerce").fillna(0)

    # load weight sheet
    if not WEIGHT_FILE.exists():
        return None, "Weight sheet not found. Generate weight sheet first."
    w = pd.read_excel(WEIGHT_FILE, engine="openpyxl")
    w["pipe_category_norm"] = w["pipe_category"].astype(str).str.strip().str.lower()
    s_long["pipe_category_norm"] = s_long["pipe_category"].astype(str).str.strip().str.lower()

    # Merge on normalized category + thickness (exact match)
    merged = pd.merge(s_long, w, how="left",
                      left_on=["pipe_category_norm", "thickness_mm"],
                      right_on=["pipe_category_norm", "thickness_mm"],
                      suffixes=("_stock", "_weight"))

    # If mass missing (likely because category text differs), try fuzzy match by pipe_category_norm containing
    missing_mass = merged["mass_kg"].isna()
    if missing_mass.any():
        # for each missing, attempt to find a weight row where weight pipe_category substring is in stock pipe_category or vice versa
        for idx in merged[missing_mass].index:
            pc = merged.at[idx, "pipe_category_norm"]
            th = merged.at[idx, "thickness_mm"]
            candidates = w[(w["thickness_mm"] == th) & (w["pipe_category_norm"].str.contains(pc, na=False))]
            if candidates.empty:
                candidates = w[(w["thickness_mm"] == th) & (pc in w["pipe_category_norm"].values)]
            if not candidates.empty:
                # pick first
                merged.at[idx, "strip_width_mm"] = candidates.iloc[0]["strip_width_mm"]
                merged.at[idx, "mass_kg"] = candidates.iloc[0]["mass_kg"]
                merged.at[idx, "pipe_category_weight"] = candidates.iloc[0]["pipe_category"]

    # fill any remaining mass_kg NaN with 0 to avoid division issues
    merged["mass_kg"] = merged["mass_kg"].fillna(0)
    merged["strip_width_mm"] = merged["strip_width_mm"].fillna(0)

    # compute stock_kg and number_of_pieces available (floor)
    merged["stock_kg"] = merged["stock_mt"].astype(float) * 1000.0
    # avoid division by zero
    merged["num_pieces_available"] = merged.apply(
        lambda r: math.floor(r["stock_kg"] / r["mass_kg"]) if r["mass_kg"] > 0 else 0,
        axis=1
    )

    # keep tidy columns
    out = merged[[
        "pipe_category", "thickness_mm", "strip_width_mm", "mass_kg",
        "stock_mt", "stock_kg", "num_pieces_available"
    ]].drop_duplicates().reset_index(drop=True)

    return out, None

# -------------------------
# Search parsing utilities
# -------------------------
def parse_search_text(text):
    """Return dict: {category_token, thickness_mm, weight_kg, qty}"""
    s = text.strip()
    out = {"raw": s, "category": None, "thickness_mm": None, "weight_kg": None, "qty": None}
    if not s:
        return out
    # weight e.g. '18kg'
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", s, flags=re.IGNORECASE)
    if m:
        out["weight_kg"] = float(m.group(1))
        s = s.replace(m.group(0), " ")
    # thickness e.g. '1.6mm' or '1.60 mm'
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", s, flags=re.IGNORECASE)
    if m2:
        out["thickness_mm"] = float(m2.group(1))
        s = s.replace(m2.group(0), " ")
    # quantity if user typed like 'x5' or 'qty 5' or trailing number
    m3 = re.search(r"(?:\bqty\b|\bx\b)?\s*(\d+)\b", s, flags=re.IGNORECASE)
    if m3:
        out["qty"] = int(m3.group(1))
        # remove this number so category parsing is cleaner
        s = re.sub(m3.group(0), " ", s, count=1, flags=re.IGNORECASE)
    # remaining tokens for category
    token = re.sub(r"[^\w\.\-xX\" ]+", " ", s).strip()
    # if token empty, fallback to raw
    out["category"] = token if token else out["raw"]
    return out

def find_best_matches(search_token, df):
    """Return rows where pipe_category contains token (case-insensitive) or vice versa"""
    t = str(search_token).strip().lower()
    if not t:
        return df
    mask = df["pipe_category"].str.lower().str.contains(t, na=False)
    res = df[mask].copy()
    if res.empty:
        # try partial token splits
        for tok in re.split(r"[\s,\/xX\"']+", t):
            tok = tok.strip()
            if not tok:
                continue
            res = df[df["pipe_category"].str.lower().str.contains(tok, na=False)]
            if not res.empty:
                break
    if res.empty:
        # as last fallback, return rows where df category is substring of token
        res = df[df["pipe_category"].str.lower().apply(lambda c: c in t)]
    return res

# -------------------------
# App UI
# -------------------------
st.title("📦 Pipe Stock & Weight — (6 m fixed length)")

col1, col2 = st.columns([3,1])
with col2:
    st.write("**Actions**")
    if st.button("🔁 Refresh data"):
        # clear caches and rerun
        build_weight_sheet.clear()
        load_and_merge_stock_with_weight.clear()
        st.experimental_rerun()
    st.write("---")
    st.write("Data files expected in `data/` folder:")
    st.write("- `width.xlsx` (strip widths)")
    st.write("- `Stocks(DD-MM-YYYY).xlsx` (daily stocks)")

# Build weight sheet
st.header("Step 1 — Build weight sheet from width.xlsx")
weight_sheet, err = build_weight_sheet()
if err:
    st.error(err)
else:
    st.success(f"Weight sheet generated ({len(weight_sheet)} rows).")
    if st.checkbox("Show weight sheet sample"):
        st.dataframe(weight_sheet.head(200))

# Merge stocks with weight
st.header("Step 2 — Merge latest Stocks file with weight sheet")
merged, err2 = load_and_merge_stock_with_weight()
if err2:
    st.error(err2)
else:
    st.success(f"Merged stock+weight rows: {len(merged)} (latest Stocks file: {find_latest_stock_file().name if find_latest_stock_file() else 'N/A'})")
    if st.checkbox("Show merged table (first 200 rows)"):
        st.dataframe(merged.head(200))

    # Download merged table
    buf = io.BytesIO()
    merged.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        label="⬇ Download merged stock report",
        data=buf,
        file_name="merged_stock_weight.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("---")
    # Search UI
    st.header("Search / Availability Check (sales)")
    q = st.text_input("Enter search (category / thickness / weight / qty). Examples: `40x40 12kg`, `2x2,18kg`, `25 NB 1.6mm`, `100x100`")
    qty_input = st.number_input("Quantity required (pieces)", min_value=1, value=1, step=1)
    if st.button("Search"):
        parsed = parse_search_text(q)
        # manual override: if user set qty_input, use that
        parsed["qty"] = int(qty_input) if qty_input else parsed.get("qty", 1)
        st.write("Parsed:", parsed)

        matches = find_best_matches(parsed["category"], merged)
        if matches.empty:
            st.warning("No matches found for that category in merged data.")
        else:
            # if thickness provided, filter
            if parsed["thickness_mm"] is not None:
                # try exact match, else nearest thickness
                t = parsed["thickness_mm"]
                exact = matches[matches["thickness_mm"] == t]
                if not exact.empty:
                    matches = exact
                    st.info(f"Matched exact thickness {t} mm")
                else:
                    # pick nearest thickness per category row
                    matches["thick_diff"] = (matches["thickness_mm"] - t).abs()
                    matches = matches.sort_values("thick_diff").groupby("pipe_category").first().reset_index()
                    st.info(f"No exact thickness found; picked nearest thickness per category.")
            # if weight provided by user, attempt to match mass_kg
            if parsed["weight_kg"] is not None:
                w = parsed["weight_kg"]
                # find rows where mass_kg approx equals user weight (within 1% or 0.5 kg)
                cand = matches[ (matches["mass_kg"].between(w*0.99, w*1.01)) | (matches["mass_kg"].between(w-0.5, w+0.5)) ]
                if not cand.empty:
                    matches = cand
                    st.info("Matched by user-provided weight.")
            # Show matches
            st.subheader("Matches")
            st.dataframe(matches[["pipe_category","thickness_mm","strip_width_mm","mass_kg","stock_mt","stock_kg","num_pieces_available"]].reset_index(drop=True))

            # For first match, show availability for requested qty
            first = matches.iloc[0]
            mass_per_item = float(first["mass_kg"])
            qty = int(parsed["qty"])
            total_weight = mass_per_item * qty
            stock_kg = float(first["stock_kg"])

            st.metric("Mass per item (kg)", f"{mass_per_item:.4f}")
            st.metric(f"Requested qty", f"{qty} pcs")
            st.metric(f"Total weight requested (kg)", f"{total_weight:.4f}")

            if stock_kg >= total_weight:
                st.success(f"Available — stock {stock_kg:.3f} kg covers requested {total_weight:.3f} kg.")
                remaining_kg = stock_kg - total_weight
                remaining_pieces = math.floor(remaining_kg / mass_per_item) if mass_per_item > 0 else 0
                st.write(f"Remaining stock after order: {remaining_kg:.3f} kg  (~{remaining_pieces} pieces)")
            else:
                st.error(f"NOT available — stock {stock_kg:.3f} kg is less than requested {total_weight:.3f} kg.")
                shortfall_kg = total_weight - stock_kg
                st.write(f"Shortfall: {shortfall_kg:.3f} kg")
            # Offer export of this single order
            order_df = pd.DataFrame([{
                "pipe_category": first["pipe_category"],
                "thickness_mm": first["thickness_mm"],
                "mass_per_item_kg": mass_per_item,
                "qty_requested": qty,
                "total_weight_kg": total_weight,
                "stock_mt": first["stock_mt"],
                "stock_kg": stock_kg,
                "available": stock_kg >= total_weight
            }])
            outbuf = io.BytesIO()
            order_df.to_excel(outbuf, index=False, engine="openpyxl")
            outbuf.seek(0)
            st.download_button("⬇ Export this order", data=outbuf, file_name="order_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Notes: 1) Keep `width.xlsx` and daily `Stocks(...)` files inside data/. 2) After pushing a new Stocks file to GitHub, press 'Refresh data' in the app. 3) The app picks the latest Stocks file by file-name sort order.")



