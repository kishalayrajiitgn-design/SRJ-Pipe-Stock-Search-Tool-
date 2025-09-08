import streamlit as st
import pandas as pd
import os

# File paths
stock_file = os.path.join("data", "Stocks(30-08-2025).xlsx")
width_file = os.path.join("data", "width.xlsx")

# Load data
@st.cache_data
def load_data():
    stocks = pd.read_excel(stock_file)
    widths = pd.read_excel(width_file)
    return stocks, widths

stocks, widths = load_data()

st.title("Pipe Stock & Weight Calculator")

# User search input
search_query = st.text_input("🔍 Enter Pipe Category (Inches / mm / NB / OD):").strip()

if search_query:
    # Filter matching rows in both sheets
    stock_matches = stocks[stocks["Pipe Category (mm / NB / OD)"].astype(str).str.contains(search_query, case=False)]
    width_matches = widths[widths["Pipe Category in  NB or  OD or mm"].astype(str).str.contains(search_query, case=False)]

    if stock_matches.empty and width_matches.empty:
        st.warning("No matching pipe category found.")
    else:
        st.subheader("📊 Stock Data (MT)")
        st.dataframe(stock_matches)

        st.subheader("📏 Strip Width Data (mm)")
        st.dataframe(width_matches)

        # Allow user to select thickness
        thickness_cols = [col for col in stock_matches.columns if "Thickness" in col]
        thickness_choice = st.selectbox("Select Thickness (mm):", options=[col.split()[1] for col in thickness_cols])

        if thickness_choice:
            # Convert thickness_choice to float
            try:
                t = float(thickness_choice)
            except:
                st.error("Invalid thickness selected.")
                st.stop()

            # Get stock (in MT) for chosen thickness
            stock_mt = stock_matches[f"Thickness {thickness_choice} mm"].sum()

            # Get width (mm) for chosen thickness
            width_col = [col for col in width_matches.columns if thickness_choice in col]
            if width_col:
                W = width_matches[width_col[0]].values[0]

                # Mass of 1 pipe (kg)
                mass_one_pipe = 0.0471 * W * t

                # Convert MT stock to number of pieces
                stock_kg = stock_mt * 1000  # 1 MT = 1000 kg
                num_pieces = stock_kg / mass_one_pipe if mass_one_pipe > 0 else 0

                st.success(f"✅ Mass of one 6m pipe: {mass_one_pipe:.2f} kg")
                st.success(f"📦 Total stock available: {stock_mt:.2f} MT ({stock_kg:.0f} kg)")
                st.success(f"🧮 Estimated number of pipes available: {num_pieces:.0f} pieces")
            else:
                st.error("Width data not found for selected thickness.")

