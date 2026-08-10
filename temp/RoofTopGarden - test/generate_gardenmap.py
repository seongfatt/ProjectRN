import os
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# 1. DATA CONFIGURATION
# ==============================================================================
PLOT_TYPES = {
    "A": {"boxes": 12, "area": 3.0, "colour": (44, 160, 44)},   # Green
    "B": {"boxes": 10, "area": 2.5, "colour": (255, 127, 14)},  # Orange
    "C": {"boxes": 9,  "area": 2.25, "colour": (31, 119, 180)}, # Blue
    "D": {"boxes": 8,  "area": 2.0, "colour": (214, 39, 40)},   # Red
}

TYPE_MAP = {
    1:"B", 2:"B", 3:"D", 4:"D", 5:"A", 6:"B", 7:"A", 8:"D", 9:"D", 10:"B",
    11:"B",12:"D",13:"D",14:"A",15:"B",16:"A",17:"D",18:"D",19:"B",20:"B",
    21:"D",22:"D",23:"A",24:"B",25:"A",26:"D",27:"D",28:"B",29:"B",30:"D",
    31:"A",32:"C",33:"D",34:"B",35:"A",36:"C",37:"C",38:"C",39:"B",40:"B",
    41:"D",42:"D",43:"A",44:"B",45:"A",46:"D",47:"D",48:"B",49:"B",50:"D",
    51:"D",52:"A",53:"B",54:"A",55:"D",56:"D",57:"B",58:"B",59:"D",60:"D",
    61:"A",62:"B",63:"A",64:"D",65:"D",66:"B",67:"B",68:"D",69:"C",70:"A",
    71:"D",72:"B",73:"C",74:"A",75:"C",76:"C"
}

PLOT_LAYOUTS = {
    "Plot 1": [[2, 3, 7, 8], [None, None, 6], [1, 4, 5, 9]],
    "Plot 2": [[11, 12, 16, 17, 20], [None, None, 15], [10, 13, 14, 18, 19]],
    "Plot 3": [[21, 24, 25, 29], [None, None, 26], [22, 23, 27, 28]],
    "Plot 4": [[None, 32, None, None, 35, 38], [30, None, 33, 34], [None, 31, None, None, 36, 37]],
    "Plot 5": [[40, 41, 45, 46], [None, None, 44], [39, 42, 43, 47]],
    "Plot 6": [[49, 50, 54, 55, 58], [None, None, 53], [48, 51, 52, 56, 57]],
    "Plot 7": [[59, 63, 64, 67], [None, 62], [60, 61, 65, 66]],
    "Plot 8": [[None, 70, None, None, 73, 76], [68, None, 71, 72], [None, 69, None, None, 74, 75]]
}

# ==============================================================================
# 2. IMAGE SETUP (GIANT SIZE FOR ELDERLY VISIBILITY)
# ==============================================================================
WIDTH, HEIGHT = 2400, 2200  # Doubled image canvas size
OUTPUT_FILENAME = "garden_giant_print.jpg"

CELL_SIZE = 80       # Giant Boxes
MARGIN = 10          
PLOT_SPACING_X = 550 # Wider spacing
PLOT_SPACING_Y = 650 # Taller spacing
LEFT_MARGIN = 120
TOP_MARGIN = 350     
LABEL_OFFSET = 100   

def draw_garden():
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to load Arial Bold; fallback to default if not found
    try:
        font_box = ImageFont.truetype("arialbd.ttf", 36)   # Big Bold Numbers
        font_label = ImageFont.truetype("arialbd.ttf", 54) # Massive Bold Plot Labels
        font_title = ImageFont.truetype("arialbd.ttf", 80) # Giant Title
        font_legend = ImageFont.truetype("arialbd.ttf", 44) 
    except:
        font_box = font_label = font_title = font_legend = ImageFont.load_default()

    # 1. Main Title
    draw.text((WIDTH//2 - 650, 80), "Community Garden Plot Layout Map", fill=(0,0,0), font=font_title)

    # 2. Draw Plots
    layout_grid = [
        ["Plot 5", "Plot 6", "Plot 7", "Plot 8"],
        ["Plot 1", "Plot 2", "Plot 3", "Plot 4"]
    ]

    for row_idx, names in enumerate(layout_grid):
        for col_idx, name in enumerate(names):
            start_x = LEFT_MARGIN + (col_idx * PLOT_SPACING_X)
            start_y = TOP_MARGIN + (row_idx * PLOT_SPACING_Y)
            
            # Draw the label ("Plot X")
            draw.text((start_x, start_y - LABEL_OFFSET), name, fill=(0,0,0), font=font_label)
            
            grid = PLOT_LAYOUTS[name]
            for r_idx, row_data in enumerate(grid):
                for c_idx, box_id in enumerate(row_data):
                    if box_id is None: continue
                    
                    bx_x1 = start_x + (c_idx * (CELL_SIZE + MARGIN))
                    bx_y1 = start_y + (r_idx * (CELL_SIZE + MARGIN))
                    bx_x2, bx_y2 = bx_x1 + CELL_SIZE, bx_y1 + CELL_SIZE
                    
                    ctype = TYPE_MAP.get(box_id)
                    color = PLOT_TYPES[ctype]["colour"]
                    
                    # Draw thick border box
                    draw.rectangle([bx_x1, bx_y1, bx_x2, bx_y2], fill=color, outline=(0,0,0), width=4)
                    
                    # Box Number centered
                    txt = str(box_id)
                    txt_color = (0,0,0) if ctype == "B" else (255,255,255)
                    # Simple text centering logic
                    w = 20 if len(txt) == 1 else 40
                    draw.text((bx_x1 + (CELL_SIZE-w)//2, bx_y1 + 15), txt, fill=txt_color, font=font_box)

    # 3. Giant Legend
    legend_y_start = TOP_MARGIN + (2 * PLOT_SPACING_Y) + 50
    draw.line([LEFT_MARGIN, legend_y_start - 50, WIDTH - LEFT_MARGIN, legend_y_start - 50], fill=(0,0,0), width=6)
    draw.text((LEFT_MARGIN, legend_y_start), "MAP LEGEND", fill=(0,0,0), font=font_label)
    
    sorted_types = sorted(PLOT_TYPES.keys())
    for idx, pt in enumerate(sorted_types):
        data = PLOT_TYPES[pt]
        ly = legend_y_start + 100 + (idx * 100)
        
        # Big Legend Swatch
        draw.rectangle([LEFT_MARGIN, ly, LEFT_MARGIN + 60, ly + 60], fill=data["colour"], outline=(0,0,0), width=3)
        draw.text((LEFT_MARGIN + 100, ly), f"Type {pt}: {data['boxes']} Boxes  |  Area: {data['area']:.2f}", fill=(0,0,0), font=font_legend)

    # Save at high quality
    img.save(OUTPUT_FILENAME, "JPEG", quality=100)
    print(f"Success! Giant map saved as: {OUTPUT_FILENAME}")

if __name__ == "__main__":
    draw_garden()