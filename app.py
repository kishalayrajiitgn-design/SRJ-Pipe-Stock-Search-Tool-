from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# Load fixed weight per pipe file (kg)
weight_df = pd.read_excel("weight_per_pipe.xlsx")

def load_stock(file_name):
    # Load daily stock file
    stock_df = pd.read_excel(file_name)
    return stock_df

def parse_input(user_input):
    """
    Parse user input formats like:
    '2x2 18kg', '40x40 12kg', '20x20 1.6mm'
    Return a dict: {'size':..., 'thickness':..., 'weight':..., 'unit':...}
    """
    input_str = user_input.lower().replace(" ", "")
    result = {"size": None, "thickness": None, "weight": None, "unit": None}
    
    # If kg is in input
    if "kg" in input_str:
        parts = input_str.split("kg")
        result["weight"] = float(parts[0].replace("x", ""))
        result["unit"] = "kg"
        if "x" in parts[0]:
            result["size"] = parts[0].split("x")[0] + "x" + parts[0].split("x")[1]
    elif "mm" in input_str:
        parts = input_str.split("mm")
        result["thickness"] = float(parts[0].split("x")[-1])
        result["size"] = parts[0].split(str(result["thickness"]))[0]
        result["unit"] = "mm"
    else:
        result["size"] = input_str
    return result

def get_weight_from_size_thickness(size, thickness):
    # Lookup weight per pipe from weight_df
    df = weight_df.copy()
    row = df[df.iloc[:, 0].astype(str).str.contains(str(size))]  # match size
    if not row.empty:
        # Find closest thickness column
        thickness_cols = [c for c in df.columns if isinstance(c, float) or c.replace('.', '', 1).isdigit()]
        closest_thickness = min(thickness_cols, key=lambda x: abs(float(x)-float(thickness)))
        weight = row[closest_thickness].values[0]
        return weight
    return None

def check_stock(stock_df, size, weight=None, thickness=None, qty_required=1):
    """
    Check stock availability in MT or pieces
    """
    df = stock_df.copy()
    
    # Filter by size
    filtered = df[df['PIPE SIZES Either in mm or NB or OD (MM =OD)'].astype(str).str.contains(size)]
    
    if filtered.empty:
        return {"available": "No", "stock_qty": 0}
    
    # Find matching column for thickness
    if thickness:
        thickness_col = min([c for c in df.columns if isinstance(c,float)], key=lambda x: abs(x-thickness))
    elif weight:
        # Convert weight to thickness using weight_df
        thickness = None
        for idx, row in weight_df.iterrows():
            if str(size) in str(row.iloc[0]):
                thickness_cols = [c for c in row.index if isinstance(c, float) or c.replace('.', '', 1).isdigit()]
                thickness_col = min(thickness_cols, key=lambda x: abs(row[x]-weight))
                break
    else:
        thickness_col = 'Grand Total'
    
    stock_qty = filtered[thickness_col].sum()
    
    return {
        "available": "Yes" if stock_qty >= qty_required else "No",
        "stock_qty": stock_qty
    }

@app.route("/", methods=["GET", "POST"])
def index():
    stock_file = "Stocks(30-08-2025).xlsx"  # Daily updated file
    stock_df = load_stock(stock_file)
    result = None
    
    if request.method == "POST":
        user_input = request.form.get("pipe_input")
        quantity = float(request.form.get("quantity"))
        parsed = parse_input(user_input)
        size = parsed["size"]
        weight = parsed.get("weight")
        thickness = parsed.get("thickness")
        
        result = check_stock(stock_df, size, weight, thickness, qty_required=quantity)
    
    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True)


