import streamlit as st
import pandas as pd
import os

# ----------------------
# File Paths
# ----------------------
STOCK_FILE = os.path.join("data", "daily_stock.xlsx")
WEIGHT_FILE = os.path.join("data", "pipe_weight.xlsx")

# ----------------------
# Load Files
# ----------------------
@st.cache_data(ttl=3600)
def load_stock():
    return pd.read_excel(STOCK_FILE, sheet_name=0)

@st.cache_data(ttl=3600)
def load_weight():
    return pd.read_excel(WEIGHT_FILE, sheet_name=0)

stock_df = load_stock()
weight_df = load_weight()

st.title("Pipe Stock Availability Checker")

# ----------------------
# User Input
# ----------------------
pipe_input = st.text_input(
    "Enter pipe (e.g., 40x40 1.6mm, 40x40 18kg, 20NB 2mm, 0.75\" 1.2mm)"
)
required_qty = st.number_input("Enter required quantity (pcs)", min_value=1, step=1)

# ----------------------
# Helper Functions
# ----------------------
def find_weight(pipe_size, thickness=None, weight=None):
    """Find weight per pipe from weight_df"""
    row = None
    if pipe_size in weight_df['Pipe Size (mm)'].values:
        row = weight_df[weight_df['Pipe Size (mm)']==pipe_size]
    elif pipe_size in weight_df['Pipe Size (NB)'].values:
        row = weight_df[weight_df['Pipe Size (NB)']==pipe_size]
    elif pipe_size in weight_df['Pipe Category (Inches)'].values:
        row = weight_df[weight_df['Pipe Category (Inches)']==pipe_size]

    if row is not None:
        if thickness and thickness in row.columns:
            return row[thickness].values[0]
        elif weight:
            return weight
    return None

def check_availability(pipe_size, thickness, qty):
    """Check stock availability"""
    weight_per_pipe = find_weight(pipe_size, thickness)
    if weight_per_pipe is None:
        return "Pipe not found in weight data", 0

    required_weight = weight_per_pipe * qty

    found_row = None
    if pipe_size in stock_df['Pipe Size  (mm / NB / OD)'].values:
        found_row = stock_df[stock_df['Pipe Size  (mm / NB / OD)']==pipe_size]
    elif pipe_size in stock_df['Pipe Category (Inches)'].values:
        found_row = stock_df[stock_df['Pipe Category (Inches)']==pipe_size]

    if found_row is not None:
        if thickness in found_row.columns:
            available_weight = found_row[thickness].values[0]
            if required_weight <= available_weight:
                return "Yes", available_weight
            else:
                return "No", available_weight
    return "Pipe not found in stock", 0

# ----------------------
# Parse Input
# ----------------------
import re

pipe_match = re.findall(r"(\d+\.?\d*)(?:x(\d+\.?\d*))?\s*(\d+\.?\d*)?(kg|mm)?", pipe_input)
if pipe_match:
    pipe_size = None
    thickness = None
    weight = None
    for match in pipe_match[0]:
        if "mm" in pipe_input:
            thickness = float(match)
        elif "kg" in pipe_input:
            weight = float(match)
        elif "x" in pipe_input:
            pipe_size = f"{match[0]}x{match[1]}"
        else:
            pipe_size = match

    if pipe_size:
        available, avail_weight = check_availability(pipe_size, str(thickness), required_qty)
        st.write(f"Available: {available}")
        st.write(f"Available stock (kg): {avail_weight}")
        if weight:
            total_weight = required_qty * weight
        else:
            total_weight = required_qty * avail_weight / required_qty
        st.write(f"Total weight for order: {total_weight} kg")


