# config.py — CLEAN VERSION (NO PROXY)
import streamlit as st
from supabase import create_client
import os
from datetime import datetime, timezone, timedelta

# ========== READ ENVIRONMENT VARIABLES ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Debug: Print to logs
print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {'*' * 30 if SUPABASE_KEY else 'MISSING'}")

# ========== CHECK CREDENTIALS ==========
if not SUPABASE_URL:
    st.error("❌ SUPABASE_URL is not set!")
    st.stop()

if not SUPABASE_KEY:
    st.error("❌ SUPABASE_KEY is not set!")
    st.stop()

# ========== CREATE SUPABASE CLIENT (NO PROXY) ==========
try:
    # ✅ NO proxy parameter!
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Test connection
    test = supabase.table('participants').select("id").limit(1).execute()
    DB_CONNECTED = True
    st.success("✅ Database connected successfully!")
    print("✅ Database connected successfully!")
except Exception as e:
    st.error(f"❌ Database connection failed: {e}")
    print(f"❌ Database connection failed: {e}")
    supabase = None
    DB_CONNECTED = False

# ========== PASSWORDS ==========
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
CHECKER_PASSWORD = os.environ.get("CHECKER_PASSWORD", "checker123")
CHAIRMAN_PASSWORD = os.environ.get("CHAIRMAN_PASSWORD", "chairman123")
APP_URL = os.environ.get("APP_URL", "https://woodlands-community-hub.onrender.com")

# ========== TIMEZONE ==========
SGT = timezone(timedelta(hours=8))

def now_sgt():
    return datetime.now(SGT)

# ========== ACTIVITIES ==========
DEFAULT_ACTIVITIES = [
    {"id": 1, "name": "Cardio Drumming", "session_1_label": "Session 1 (7PM-8PM)", "session_2_label": "Session 2 (8PM-9PM)", "active": True},
]

def load_activities():
    if not DB_CONNECTED:
        return DEFAULT_ACTIVITIES
    try:
        r = supabase.table('activities').select("*").eq('active', True).order('id').execute()
        return r.data if r.data else DEFAULT_ACTIVITIES
    except:
        return DEFAULT_ACTIVITIES

def refresh_data():
    st.cache_data.clear()
    st.cache_resource.clear()

# ========== PLOT TYPES ==========
PLOT_TYPES = {
    "A": {"area": 3.0, "colour": "#2ca02c", "total": 16, "boxes": 12},
    "B": {"area": 2.5, "colour": "#ff7f0e", "total": 24, "boxes": 10},
    "C": {"area": 2.25, "colour": "#1f77b4", "total": 8, "boxes": 9},
    "D": {"area": 2.0, "colour": "#d62728", "total": 28, "boxes": 8},
}
TOTAL_PLOTS = 76

TYPE_MAP = {
    1: "B", 2: "B", 3: "D", 4: "D", 5: "A", 6: "B", 7: "A", 8: "D", 9: "D", 10: "B",
    11: "B", 12: "D", 13: "D", 14: "A", 15: "B", 16: "A", 17: "D", 18: "D", 19: "B", 20: "B",
    21: "D", 22: "D", 23: "A", 24: "B", 25: "A", 26: "D", 27: "D", 28: "B", 29: "B", 30: "D",
    31: "A", 32: "C", 33: "D", 34: "B", 35: "A", 36: "C", 37: "C", 38: "C", 39: "B", 40: "B",
    41: "D", 42: "D", 43: "A", 44: "B", 45: "A", 46: "D", 47: "D", 48: "B", 49: "B", 50: "D",
    51: "D", 52: "A", 53: "B", 54: "A", 55: "D", 56: "D", 57: "B", 58: "B", 59: "D", 60: "D",
    61: "A", 62: "B", 63: "A", 64: "D", 65: "D", 66: "B", 67: "B", 68: "D", 69: "C", 70: "A",
    71: "D", 72: "B", 73: "C", 74: "A", 75: "C", 76: "C"
}

# ========== MOBILE CSS ==========
MOBILE_CSS = """<style>
@media(max-width:768px){
    body{min-width:100vw!important; max-width:100vw!important; overflow-x:hidden!important;}
    .main .block-container{padding:0.3rem!important; max-width:100vw!important; width:100vw!important;}
    [data-testid="stSidebar"]{display:none!important;}
    [data-testid="stSidebarCollapseButton"]{display:none!important;}
    [data-testid="collapsedControl"]{display:none!important;}
    .element-container{width:100%!important; max-width:100%!important;}
    .stMarkdown{width:100%!important;}
    h1{font-size:17px!important; margin:4px 0!important;}
    h2{font-size:15px!important; margin:3px 0!important;}
    h3{font-size:13px!important;}
    p, li{font-size:13px!important; line-height:1.4!important;}
    .stButton>button{
        width:100%!important;
        font-size:15px!important;
        padding:14px!important;
        min-height:48px!important;
        border-radius:8px!important;
        margin:4px 0!important;
    }
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select,
    .stTextArea>div>div>textarea{
        font-size:16px!important;
        padding:12px!important;
        min-height:48px!important;
    }
    .stRadio [role="radiogroup"]{flex-direction:column!important;}
    .stRadio [role="radiogroup"] label{margin:3px 0!important; padding:6px!important;}
    .stTabs [data-baseweb="tab-list"]{overflow-x:auto!important; flex-wrap:nowrap!important;}
    .stTabs [data-baseweb="tab-list"] button{font-size:11px!important; padding:6px 8px!important; white-space:nowrap!important;}
    .stColumns{flex-direction:column!important;}
    .stColumns > div{width:100%!important; flex:none!important; max-width:100%!important; margin:2px 0!important;}
    .stMetric{padding:4px!important;}
    .stMetric label{font-size:10px!important;}
    .stMetric .css-1xarl3l{font-size:16px!important;}
    .stDataFrame{font-size:11px!important;}
    .stDataFrame > div{overflow-x:auto!important;}
    img{max-width:100%!important; height:auto!important;}
    .streamlit-expanderHeader{font-size:13px!important; padding:10px!important;}
    .main > div{padding-left:0!important; padding-right:0!important;}
}
.pdpa-notice{
    background: #1a1a2e;
    border-left: 4px solid #ffc107;
    color: #ffffff;
    padding: 10px;
    border-radius: 4px;
    margin: 8px 0;
    font-size: 13px;
}
</style>"""