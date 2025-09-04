import os, glob, re
import pandas as pd
import streamlit as st

# ----------------------------
# CONFIG FILES
# ----------------------------
WEIGHT_FILE = "data/weight per pipe (kg).xlsx"

# ----------------------------
# NORMALIZATION
# ----------------------------
def normalize_name(s):
    """Standardize pipe names for matching"""
    if not isinstance(s, str): return s
    s = s.strip().lower()
    s = s.replace(" ", "")
    s = s.replace("×", "x")
    s = s.replace("nb", "NB")
    s = s.replace("od", "OD")
    return s

# ----------------------------
# LOAD WEIGHT DATA
# ----------------------------
def load_weight_data():
    df = pd.read_excel(WEIGHT_FILE)
    df = df.applymap(lambda x: normalize_name(x) if isinstance(x, str) else x)
    return df

# ----------------------------
# LOAD LATEST STOCK DATA
# ----------------------------
def get_latest_stock_file():
    stock_files = glob.glob("data/Stocks*.xlsx")
    return max(stock_files, key=os.path.getctime) if stock_files else None

def load_stock_data():
    latest_file = get_latest_stock_file()
    if not latest_file: return None, None
    df = pd.read_excel(latest_file, sheet_name="Table 1")
    df = df.applymap(lambda x: normalize_name(x) if isinstance(x, str) else x)
    return df, os.path.basename(latest_file)

# ----------------------------
# PARSE USER INPUT
# ----------------------------
def parse_input(user_text):
    user_text = user_text.strip()

    # thickness in mm
    th_match = re.search(r"([\d.]+)\s*mm", user_text.lower())
    thickness = float(th_match.group(1)) if th_match else None

    # weight in kg
    wt_match = re.search(r"([\d.]+)\s*kg", user_text.lower())
    weight = float(wt_match.group(1)) if wt_match else None

    # pipe size = everything before first space/comma/number
    pipe_size = re.split(r"[ ,]", user_text)[0]
    pipe_size = normalize_name(pipe_size)

    return pipe_size, thickness, weight

# ----------------------------
# FIND WEIGHT PER PIPE
# ----------------------------
def find_weight(weight_df, pipe_size, thickness=None, weight=None):
    norm_pipe = normalize_name(pipe_size)

    row = weight_df[
        weight_df.astype(str).apply(
            lambda x: any(normalize_name(v) == norm_pipe for v in x.values),
            axis=1,
        )
    ]
    if row.empty: return None, None

    # Map thickness cols
    thickness_cols = {}
    for col in row.columns[3:]:
        try:
            thickness_cols[float(col)] = col
        except: pass

    if thickness:
        # exact or nearest thickness
        available = sorted(thickness_cols.keys())
        closest = min(available, key=lambda x: abs(x-thickness))
        chosen_col = thickness_cols[closest]
        return closest, float(row[chosen_col].values[0])

    elif weight:
        # reverse lookup: match by per-pipe weight
        best = None; min_diff = 999
        for t, col in thickness_cols.items():
            try:
                val = float(row[col].values[0])
                if abs(val-weight) < min_diff:
                    min_diff = abs(val-weight)
                    best = (t, val)
            except: pass
        return best if best else (None, None)

    return None, None

# ----------------------------
# STREAMLIT APP
# ----------------------------
st.title("📊 Pipe Stock Availability Checker")

weight_df = load_weight_data()
stock_df, stock_file = load_stock_data()

if stock_df is None:
    st.error("❌ No stock file found. Upload one in /data/")
    st.stop()
else:
    st.success(f"✅ Using stock file: {stock_file}")

pipe_input = st.text_input(
    "Enter pipe (e.g. 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 0.75\" 1.2mm)"
)
quantity = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

if st.button("Check Availability") and pipe_input:
    pipe_size, thickness, weight = parse_input(pipe_input)

    thickness, per_pipe_kg = find_weight(weight_df, pipe_size, thickness, weight)
    if not per_pipe_kg:
        st.error("❌ Pipe size or thickness not found in weight table.")
        st.stop()

    # Check stock
    if str(thickness) in stock_df.columns:
        stock_row = stock_df[
            stock_df.astype(str).apply(
                lambda x: any(normalize_name(v) == pipe_size for v in x.values),
                axis=1,
            )
        ]
        if not stock_row.empty:
            stock_mt = stock_row[str(thickness)].values[0]
            stock_kg = stock_mt * 1000
            available_pcs = int(stock_kg / per_pipe_kg)
            order_kg = quantity * per_pipe_kg

            st.info(f"🔎 Pipe: **{pipe_size}** | Thickness: **{thickness} mm**")
            st.info(f"⚖️ Per Pipe Weight: **{per_pipe_kg:.2f} kg**")
            st.info(f"📦 Stock: **{stock_mt:.2f} MT ({available_pcs} pcs)**")

            if available_pcs >= quantity:
                st.success(f"✅ Yes! {quantity} pcs (~{order_kg:.2f} kg) available.")
            else:
                st.warning(f"⚠️ Only {available_pcs} pcs (~{stock_kg:.2f} kg) available, requested {quantity}.")
        else:
            st.error("❌ Pipe size not in stock file.")
    else:
        st.error("❌ Thickness not in stock file.")
