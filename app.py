import os, glob, re
import pandas as pd
import streamlit as st

# ---------------- CONFIG ----------------
WEIGHT_FILE = "data/weight per pipe (kg).xlsx"

# ------------- HELPERS ------------------
def normalize(s):
    """Standardize names for matching"""
    if not isinstance(s, str): return s
    s = s.strip().lower()
    s = s.replace("×", "x")
    s = s.replace(" ", "")
    s = s.replace("nb", "nb")
    s = s.replace("od", "od")
    return s

def get_latest_stock_file():
    files = glob.glob("data/Stocks*.xlsx")
    if not files: return None
    return max(files, key=os.path.getctime)

# Load fixed weight data
def load_weight():
    df = pd.read_excel(WEIGHT_FILE)
    df = df.applymap(lambda x: normalize(x) if isinstance(x, str) else x)
    return df

# Load latest stock data
def load_stock():
    latest = get_latest_stock_file()
    if not latest: return None, None
    df = pd.read_excel(latest, sheet_name=0)
    df = df.applymap(lambda x: normalize(x) if isinstance(x, str) else x)
    return df, os.path.basename(latest)

# Parse user input
def parse_query(q):
    q = q.strip()
    th = re.search(r"([\d.]+)\s*mm", q.lower())
    thickness = float(th.group(1)) if th else None
    wt = re.search(r"([\d.]+)\s*kg", q.lower())
    weight = float(wt.group(1)) if wt else None
    size = re.split(r"[ ,]", q)[0]
    return normalize(size), thickness, weight

# Find per pipe weight
def find_weight(df, size, thickness=None, weight=None):
    norm = normalize(size)
    row = df[df.astype(str).apply(lambda x: any(normalize(v)==norm for v in x.values), axis=1)]
    if row.empty: return None, None

    # thickness mapping
    th_map = {}
    for col in row.columns[3:]:
        try: th_map[float(col)] = col
        except: continue
    if not th_map: return None, None

    if thickness:
        avail = sorted(th_map.keys())
        closest = min(avail, key=lambda x: abs(x-thickness))
        return closest, float(row[th_map[closest]].values[0])

    if weight:
        best = None; diff = 999
        for t,c in th_map.items():
            try:
                val = float(row[c].values[0])
                if abs(val-weight)<diff:
                    diff = abs(val-weight); best=(t,val)
            except: continue
        return best if best else (None,None)

    return None, None

# ---------------- STREAMLIT APP ----------------
st.title("📊 Pipe Stock Availability Checker")

weight_df = load_weight()
stock_df, stock_file = load_stock()

if stock_df is None:
    st.error("❌ No stock file found in /data/")
    st.stop()
else:
    st.success(f"✅ Using stock file: {stock_file}")

query = st.text_input("Enter pipe (e.g. 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 0.75\" 1.2mm)")
qty = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

if st.button("Check Availability") and query:
    size, th, wt = parse_query(query)
    th, per_pipe = find_weight(weight_df, size, th, wt)

    if not per_pipe:
        st.error("❌ Pipe size or thickness/weight not found in weight table.")
        st.stop()

    # check stock file
    if str(th) in stock_df.columns:
        srow = stock_df[stock_df.astype(str).apply(lambda x: any(normalize(v)==size for v in x.values), axis=1)]
        if not srow.empty:
            stock_mt = float(srow[str(th)].values[0])
            stock_kg = stock_mt*1000
            avail_pcs = int(stock_kg/per_pipe)
            req_kg = qty*per_pipe

            st.write(f"🔎 Pipe: **{size}**, Thickness: **{th} mm**")
            st.write(f"⚖️ Per Pipe Weight: **{per_pipe:.2f} kg**")
            st.write(f"📦 Stock: **{stock_mt:.2f} MT = {stock_kg:.1f} kg = {avail_pcs} pcs**")
            st.write(f"🛒 Order: **{qty} pcs = {req_kg:.1f} kg**")

            if avail_pcs>=qty:
                st.success("✅ Yes, available")
            else:
                st.warning(f"⚠️ Only {avail_pcs} pcs available, requested {qty}")
        else:
            st.error("❌ Pipe size not in stock file.")
    else:
        st.error("❌ Thickness not in stock file.")

