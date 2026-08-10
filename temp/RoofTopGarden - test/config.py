# config.py - Supabase Configuration for Rooftop Garden
import streamlit as st
from supabase import create_client
import os

# ========== DATABASE CONFIG ==========
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

@st.cache_resource
def get_db():
    """Initialize Supabase connection"""
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return client, True
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None, False

supabase, DB_CONNECTED = get_db()

def refresh_data():
    """Clear all caches to reload fresh data"""
    st.cache_data.clear()

# ========== GARDEN CONFIGURATION ==========
PLOT_TYPES = {
    "A": {"boxes": 12, "area": 3.0, "colour": "#2ca02c", "total": 16},   # Green
    "B": {"boxes": 10, "area": 2.5, "colour": "#ff7f0e", "total": 24},   # Orange
    "C": {"boxes": 9,  "area": 2.25, "colour": "#1f77b4", "total": 8},   # Blue
    "D": {"boxes": 8,  "area": 2.0, "colour": "#d62728", "total": 28},   # Red
}

TOTAL_PLOTS = 76
ADMIN_PASSWORD = "gardenadmin"

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