import streamlit as st
import pandas as pd
import io

# Density of mild steel (g/cm³) = 7.85 -> 7850 kg/m³
DENSITY = 7850  

# Function to calculate pipe weight
def calculate_pipe_weight(strip_width_mm, thickness_mm, length_m=6):
    # Convert mm to meters
    strip_width_m = strip_width_mm / 1000
    thickness_m = thickness_mm / 1000

    # Volume = width × thickness × length
    volume_m3 = strip_width_m * thickness_m * length_m  

    # Mass = density × volume
    mass_kg = DENSITY * volume_m3  
    return mass_kg

# Create weight sheet DataFrame
def create_weight_sheet(strip_widths, thicknesses, length_m=6):
    records = []
    for w in strip_widths:
        for t in thicknesses:
            weight = calculate_pipe_weight(w, t, length_m)
            records.append({
                "Strip Width (mm)": w,
                "Thickness (mm)": t,
                "Length (m)": length_m,
                "Weight (kg)": round(weight, 2)
            })
    return pd.DataFrame(records)

# -------------------- Streamlit UI --------------------

st.title("📊 Pipe Stock Management Tool")

# User input
st.sidebar.header("Input Parameters")
length_m = st.sidebar.number_input("Pipe Length (m)", value=6.0, step=0.5)
strip_widths = st.sidebar.text_input("Enter strip widths (mm, comma separated)", "100, 120, 150")
thicknesses = st.sidebar.text_input("Enter thicknesses (mm, comma separated)", "1.2, 2.5, 5")

# Convert inputs to lists
try:
    strip_widths = [float(x.strip()) for x in strip_widths.split(",")]
    thicknesses = [float(x.strip()) for x in thicknesses.split(",")]
except:
    st.error("⚠️ Please enter valid numbers for strip widths and thicknesses.")
    st.stop()

# Generate DataFrame
st.subheader("Calculated Pipe Weights")
result_df = create_weight_sheet(strip_widths, thicknesses, length_m)
st.dataframe(result_df, use_container_width=True)

# Excel download
output = io.BytesIO()
result_df.to_excel(output, index=False, engine="openpyxl")
output.seek(0)

st.download_button(
    label="📥 Download as Excel",
    data=output,
    file_name="pipe_stock.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
