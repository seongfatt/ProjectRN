# config.py
import os

# ---------- CONFIG ----------
PLOT_TYPES = {
    "A": {"boxes": 12, "area": 3.0, "colour": "#2ca02c", "total": 16},  # Green
    "B": {"boxes": 10, "area": 2.5, "colour": "#ff7f0e", "total": 24},  # Orange
    "C": {"boxes": 9,  "area": 2.25, "colour": "#1f77b4", "total": 8},   # Blue
    "D": {"boxes": 8,  "area": 2.0, "colour": "#d62728", "total": 28},   # Red
}
CSV_FILE = "garden_roster.csv"
TOTAL_PLOTS = 76

# ---------- PHYSICAL LAYOUT ----------
layout_order = [
    7, 2, 3, 6, 8, 1, 4, 9, 5,
    16, 11, 12, 15, 17, 20, 10, 13, 18, 19, 14,
    25, 21, 24, 26, 29, 22, 27, 28, 23,
    30, 32, 33, 34, 35, 38, 31, 36, 37,
    45, 40, 41, 44, 46, 39, 42, 47, 43,
    54, 49, 50, 53, 55, 58, 48, 51, 56, 57, 52,
    63, 59, 62, 64, 67, 60, 65, 66, 61,
    68, 70, 71, 72, 73, 76, 69, 74, 75
]

# ---------- TYPE MAP ----------
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

# ---------- CUSTOM LAYOUT STRUCTURE ----------
PLOT_LAYOUTS = {
    "Plot 1": [
        [2, 3, 7, 8, None, None, None, None, None, None],
        [None, None, 6, None, None, None, None, None, None, None],
        [1, 4, 5, 9, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 2": [
        [11, 12, 16, 17, 20, None, None, None, None, None],
        [None, None, 15, None, None, None, None, None, None, None],
        [10, 13, 14, 18, 19, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 3": [
        [21, 24, 25, 29, None, None, None, None, None, None],
        [None, None, 26, None, None, None, None, None, None, None],
        [22, 23, 27, 28, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 4": [
        [None, 32, None, None, 35, 38, None, None, None, None],
        [30, None, 33, 34, None, None, None, None, None, None],
        [None, 31, None, None,36, 37, None, None, None]
    ],
    "Plot 5": [
        [40, 41, 45, 46, None, None, None, None, None, None],
        [None, None, 44, None, None, None, None, None, None, None],
        [39, 42, 43, 47, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 6": [
        [49, 50, 54, 55, 58, None, None, None, None, None],
        [None, None, 53, None, None, None, None, None, None, None],
        [48, 51, 52, 56, 57, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 7": [
        [59, 63, 64, 67, None, None, None, None, None, None],
        [None, 62, None, None, None, None, None, None, None, None],
        [60, 61, 65, 66, None, None, None, None, None, None],
        [None, None, None, None, None, None, None, None, None, None]
    ],
    "Plot 8": [
        [None, 70, None, None, 73, 76, None, None, None, None],
        [68, None, 71, 72, None, None, None, None, None, None],
        [None, 69, None, None, 74, 75, None, None, None, None],
    ]
}

all_plots = set(range(1, 77))
missing = sorted(list(all_plots - set(layout_order)))
PHYSICAL_ORDER = layout_order + missing[:76 - len(layout_order)]
# config.py - Add at the end:
HF_REPO_ID = "wrnz6/garden-data"  # ⭐ CHANGE THIS ⭐

# ✅ VALIDATION — ADD THIS HERE
assert len(PHYSICAL_ORDER) == 76, f"Expected 76 plots, got {len(PHYSICAL_ORDER)}"
assert len(set(PHYSICAL_ORDER)) == 76, "Duplicate plot numbers found!"
assert min(PHYSICAL_ORDER) == 1 and max(PHYSICAL_ORDER) == 76, "Plots must be numbered 1–76"