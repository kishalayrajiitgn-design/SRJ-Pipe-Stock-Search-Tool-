# app.py
import pandas as pd
import streamlit as st

# Load Excel files from data folder
weight_df = pd.read_excel("data/weight_per_pipe.xlsx")
stocks_df = pd.read_excel("data/Stocks(30-08-2025).xlsx")

st.set_page_config(page_title="Pipe Stock Checker", layout="wide")
st.title("🔍 Pipe Stock Availability Checker")

# Input for pipe
pipe_input = st.text_input(
    "Enter pipe (e.g., 40x40 1.6mm, 25NB 5.7kg)", 
    ""
)

# Input for quantity
qty_input = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

if st.button("Check Stock"):
    if not pipe_input:
        st.warning("Please enter a pipe specification.")
    else:
        # Filter stocks_df for the given pipe
        stock_row = stocks_df[stocks_df['Pipe Category'].str.contains(pipe_input, case=False, na=False)]
        if stock_row.empty:
            st.error("Pipe not found in stock!")
        else:
            available_qty = stock_row.iloc[0]['Stock (MT)']
            
            # Convert weight if pipe input is in kg
            if "kg" in pipe_input.lower():
                weight_row = weight_df[weight_df['Pipe'].str.contains(pipe_input.split()[0], case=False, na=False)]
                if not weight_row.empty:
                    weight_per_piece = weight_row.iloc[0]['Weight (kg)']
                    available_pcs = int((available_qty * 1000) / weight_per_piece)
                else:
                    st.warning("Weight data not found, showing stock in MT.")
                    available_pcs = None
            else:
                available_pcs = None

            st.write(f"**Available stock:** {available_qty} MT")
            if available_pcs is not None:
                st.write(f"**Available stock in pieces:** {available_pcs} pcs")
            
            if qty_input:
                if available_pcs is not None:
                    if qty_input <= available_pcs:
                        st.success("✅ Stock available!")
                    else:
                        st.error("❌ Not enough stock!")
                else:
                    st.info("Stock quantity in pieces not available; check MT stock.")



