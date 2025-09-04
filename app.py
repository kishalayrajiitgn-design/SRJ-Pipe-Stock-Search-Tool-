import streamlit as st
import pandas as pd
import glob
import os
from datetime import datetime

# ---------------------------
# Helper Functions
# ---------------------------
def load_latest_stock():
    # Get the latest stock file in the data folder
    files = glob.glob("data/Stocks(*).xlsx")
    if not files:
        st.error("No stock files found in the data folder!")
        return None
    latest_file = max(files, key=os.path.getctime)
    df_stock = pd.read_excel(latest_file)
    return df_stock, latest_file

def load_weight_data():
    df_weight = pd.read_excel("data/weight_per_pipe.xlsx")
    return df_weight

def parse_user_input(user_input):
    # Clean and split input for parsing
    user_input = user_input.replace(" ", "").upper()
    return user_input

def match_pipe(user_input, df_weight):
    """
    Match pipe input with weight table to get weight per unit.
    user_input can be in multiple formats:
    - 2x2 18kg
    - 40x40 12kg
    - 20NB 1.6mm
    - inch + thickness
    - mm + thickness
    """
    matched_row = None
    for _, row in df_weight.iterrows():
        # Check for inch match
        if "INCH" in user_input or '"' in user_input or "'" in user_input:
            if str(row["Pipe Category (Inches)"]).replace('"','').upper() in user_input:
                matched_row = row
                break
        # Check for NB
        if "NB" in user_input:
            if str(row.get("Pipe Size  ( NB)", "")).upper() in user_input:
                matched_row = row
                break
        # Check for mm
        if any(c.isdigit() for c in user_input) and "NB" not in user_input:
            if str(row.get("Pipe Size (mm)", "")).replace(" ","") in user_input:
                matched_row = row
                break
    return matched_row

def find_thickness_weight(thickness, matched_row):
    """
    Match thickness to get weight per pipe.
    Thickness can be in mm or kg.
    """
    if thickness.endswith("MM"):
        thickness_value = thickness.replace("MM", "")
        col_name = f"Thickness {thickness_value} mm"
        if col_name in matched_row.index:
            return matched_row[col_name]
    elif thickness.endswith("KG"):
        # Weight directly
        return float(thickness.replace("KG", ""))
    else:
        return None

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(page_title="Pipe Stock Checker", layout="wide")
st.title("🔍 Pipe Stock Availability Checker")

# Load data
df_stock, latest_file = load_latest_stock()
df_weight = load_weight_data()

st.info(f"Using stock file: **{os.path.basename(latest_file)}**")

# User Input
user_input = st.text_input("Enter Pipe (e.g., 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 0.75\" 1.2mm)")
required_qty = st.number_input("Enter Quantity Required (pcs)", min_value=1, step=1)

if st.button("Check Availability"):

    if not user_input:
        st.warning("Please enter a pipe specification.")
    else:
        user_input_clean = parse_user_input(user_input)
        matched_row = match_pipe(user_input_clean, df_weight)

        if matched_row is None:
            st.error("Pipe specification not found in weight table!")
        else:
            # Identify thickness
            thickness = ""
            for word in user_input_clean.split():
                if "MM" in word or "KG" in word:
                    thickness = word
                    break
            if not thickness:
                st.warning("Thickness or weight not provided in input.")
            else:
                weight_per_pipe = find_thickness_weight(thickness, matched_row)
                if weight_per_pipe is None:
                    st.error("Weight/Thickness not found for the given pipe.")
                else:
                    # Match with daily stock
                    pipe_size_stock_col = "Pipe Size  (mm / NB / OD)"
                    pipe_category_col = "Pipe Category (Inches)"
                    
                    df_filtered = df_stock[
                        (df_stock[pipe_category_col].astype(str).str.upper() == str(matched_row[pipe_category_col]).upper()) &
                        (df_stock[pipe_size_stock_col].astype(str).str.upper() == str(matched_row.get("Pipe Size (mm)", matched_row.get("Pipe Size  ( NB)",""))).upper())
                    ]

                    thickness_col = [col for col in df_stock.columns if str(weight_per_pipe) in str(col) or "Thickness" in col]
                    if not thickness_col:
                        st.warning("No matching thickness column in stock file")
                        available_qty = 0
                    else:
                        available_qty = df_filtered[thickness_col[0]].sum() if not df_filtered.empty else 0

                    total_weight = weight_per_pipe * required_qty

                    st.write("### ✅ Result")
                    st.write(f"Pipe: {user_input}")
                    st.write(f"Weight per pipe: {weight_per_pipe:.3f} kg")
                    st.write(f"Required Quantity: {required_qty} pcs")
                    st.write(f"Total Weight: {total_weight:.3f} kg")

                    if available_qty >= required_qty:
                        st.success(f"Available: YES ✅ (Stock: {available_qty} pcs)")
                    else:
                        st.error(f"Available: NO ❌ (Stock: {available_qty} pcs)")

st.markdown("---")
st.markdown("Developed for sales team to quickly check pipe availability and weight.")

