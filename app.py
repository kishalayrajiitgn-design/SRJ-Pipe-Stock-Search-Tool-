import os, glob, re
import pandas as pd
import streamlit as st

# --- Constants ---
WEIGHT_FILE = "data/weight per pipe (kg).xlsx"

# --- Normalization Helper ---
def normalize_pipe_name(name):
    """Standardize pipe names for matching"""
    s = str(name).strip().lower()
    s = s.replace(" ", "")        # remove spaces
    s = s.replace("x", "×")       # ensure × instead of x
    s = s.replace("nb", "NB")     # NB uppercase
    s = s.replace("od", "OD")     # OD uppercase
    return s

# --- Load Weight File (fixed master) ---
def load_weight_data():
    df = pd.read_excel(WEIGHT_FILE)
    # Normalize NB column (3rd col usually has NB sizes)
    if df.shape[1] >= 3:
        df.iloc[:,2] = df.iloc[:,2].apply(lambda x: normalize_pipe_name(x) if pd.notna(x) else x)
    return df

# --- Find latest Stock File (daily) ---
def get_latest_stock_file():
    stock_files = glob.glob("data/Stocks*.xlsx")
    if not stock_files:
        return None
    return max(stock_files, key=os.path.getctime)

# --- Load Stock Data ---
def load_stock_data():
    latest_file = get_latest_stock_file()
    if latest_file and os.path.exists(latest_file):
        df = pd.read_excel(latest_file, sheet_name="Table 1")
        # Normalize pipe size column (first column)
        df.iloc[:,0] = df.iloc[:,0].apply(normalize_pipe_name)
        return df, latest_file
    return None, None

# --- Parse user input ---
def parse_input(user_text):
    user_text = user_text.strip()

    # Extract thickness (mm) or weight (kg)
    thickness_match = re.search(r"([\d.]+)\s*mm", user_text.lower())
    weight_match = re.search(r"([\d.]+)\s*kg", user_text.lower())

    thickness = float(thickness_match.group(1)) if thickness_match else None
    weight = float(weight_match.group(1)) if weight_match else None

    # Extract pipe size (before space/comma)
    pipe_size = re.split(r"[ ,]", user_text)[0]
    pipe_size = normalize_pipe_name(pipe_size)
    return pipe_size, thickness, weight

# --- Match pipe size in weight file ---
def find_weight_per_pipe(weight_df, pipe_size, thickness=None, weight=None):
    norm_pipe = normalize_pipe_name(pipe_size)

    # Find row with normalized NB column
    row = weight_df[
        weight_df.astype(str).apply(lambda x: any(normalize_pipe_name(val) == norm_pipe for val in x.values), axis=1)
    ]
    if row.empty:
        return None, None

    if thickness:
        if str(thickness) in row.columns:
            return thickness, row[str(thickness)].values[0]
    elif weight:
        for col in row.columns[3:]:
            try:
                if abs(float(row[col].values[0]) - weight) < 0.5:
                    return float(col), row[col].values[0]
            except:
                continue
    return None, None

# --- Streamlit App ---
st.title("📊 Pipe Stock Availability Checker")

# Load master weight data
weight_df = load_weight_data()

# Load daily stock data
stock_df, stock_file = load_stock_data()
if stock_df is None:
    st.error("❌ No daily stock file found in 'data/'. Please upload.")
    uploaded_file = st.file_uploader("Upload today's stock file", type="xlsx")
    if uploaded_file:
        stock_df = pd.read_excel(uploaded_file, sheet_name="Table 1")
        stock_df.iloc[:,0] = stock_df.iloc[:,0].apply(normalize_pipe_name)
        st.success("✅ Stock file uploaded successfully!")
    else:
        st.stop()
else:
    st.success(f"✅ Using stock file: {os.path.basename(stock_file)}")

# --- User Input ---
pipe_input = st.text_input(
    "Enter pipe (e.g. `40x40 1.6mm`, `40x40 18kg`, `20NB 2mm`, `19.05 OD 1.2mm`)"
).strip()
quantity = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

# --- Process Search ---
if st.button("Check Availability") and pipe_input:
    pipe_size, thickness, weight = parse_input(pipe_input)

    # Find weight per pipe
    thickness, weight_per_pipe = find_weight_per_pipe(weight_df, pipe_size, thickness, weight)

    if not weight_per_pipe:
        st.error("❌ Pipe size or thickness/weight not found in weight table.")
        st.stop()

    # Find stock (MT) for that pipe size + thickness
    if thickness and str(thickness) in stock_df.columns:
        stock_row = stock_df[
            stock_df.astype(str).apply(lambda x: any(normalize_pipe_name(val) == pipe_size for val in x.values), axis=1)
        ]
        if not stock_row.empty:
            stock_mt = stock_row[str(thickness)].values[0]
            stock_kg = stock_mt * 1000
            available_pcs = int(stock_kg / weight_per_pipe)
            order_weight = quantity * weight_per_pipe

            st.info(f"🔎 Pipe Size: **{pipe_size}** | Thickness: **{thickness} mm**")
            st.info(f"⚖️ Weight per pipe: **{weight_per_pipe:.2f} kg**")
            st.info(f"📦 Total stock: **{stock_mt:.2f} MT ({available_pcs} pcs)**")

            if available_pcs >= quantity:
                st.success(
                    f"✅ Available! {available_pcs} pcs in stock. "
                    f"Requested: {quantity} pcs (~{order_weight:.2f} kg)"
                )
            else:
                st.warning(
                    f"⚠️ Not enough stock. Only {available_pcs} pcs available "
                    f"(~{stock_kg:.2f} kg), requested {quantity} pcs "
                    f"(~{order_weight:.2f} kg)."
                )
        else:
            st.error("❌ Pipe size not found in stock sheet.")
    else:
        st.error("❌ Thickness column not found in stock sheet.")
