import os
import streamlit as st
import logging
from supabase import create_client
from datetime import timezone, timedelta, datetime

logger = logging.getLogger("community_hub.config")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def get_secret(key, default=None):
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    env_value = os.environ.get(key)
    if env_value is not None:
        return env_value
    return default

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD")
CHECKER_PASSWORD = get_secret("CHECKER_PASSWORD")
CHAIRMAN_PASSWORD = get_secret("CHAIRMAN_PASSWORD")
APP_URL = get_secret("APP_URL", "https://woodlands-community-hub.onrender.com")

supabase = None
DB_CONNECTED = False
DB_ERROR_MSG = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        DB_CONNECTED = True
        logger.info("Supabase client created (connection will be verified on first query).")
    except Exception as e:
        DB_ERROR_MSG = str(e)
        logger.error(f"Supabase client creation failed: {e}")
else:
    DB_ERROR_MSG = "Missing SUPABASE_URL or SUPABASE_KEY"
    logger.error(DB_ERROR_MSG)

def try_reconnect():
    global supabase, DB_CONNECTED, DB_ERROR_MSG
    if DB_CONNECTED and supabase is not None:
        return True
    if not SUPABASE_URL or not SUPABASE_KEY:
        DB_ERROR_MSG = "Missing SUPABASE_URL or SUPABASE_KEY"
        DB_CONNECTED = False
        return False
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        supabase.table("participants").select("id").limit(1).execute()
        DB_CONNECTED = True
        DB_ERROR_MSG = None
        logger.info("✅ Supabase (re)connected successfully!")
        return True
    except Exception as e:
        DB_CONNECTED = False
        DB_ERROR_MSG = str(e)
        logger.error(f"❌ Supabase reconnect failed: {e}")
        return False

# ... (Keep your existing MOBILE_CSS, PLOT_TYPES, load_activities, etc. here) ...

# ========== ENVIRONMENT HELPERS ==========
def is_production():
    """True when running on Render, Streamlit Cloud, HF Spaces, or ENVIRONMENT=production."""
    return bool(
        os.environ.get("RENDER")
        or os.environ.get("STREAMLIT_SHARING")
        or os.environ.get("STREAMLIT_CLOUD")
        or os.environ.get("SPACE_ID")  # HF Spaces
        or os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")
    )

# ========== TIMEZONE ==========
SGT = timezone(timedelta(hours=8))

def now_sgt():
    """Return current datetime in Singapore Time (UTC+8)."""
    return datetime.now(SGT)

# ========== CACHE MANAGEMENT ==========
def refresh_data():
    """Clear all cached data. Use sparingly — this is a sledgehammer."""
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass

# ========== ACTIVITIES ==========
DEFAULT_ACTIVITIES = [
    {"id": 1, "name": "Cardio Drumming", "session_1_label": "Session 1 (7PM-8PM)", "session_2_label": "Session 2 (8PM-9PM)", "active": True},
]

@st.cache_data(ttl=300, show_spinner=False)
def load_activities():
    """Load active activities. Cached for 5 minutes; bust with refresh_data()."""
    if not DB_CONNECTED or supabase is None:
        return DEFAULT_ACTIVITIES
    try:
        r = supabase.table("activities").select("*").eq("active", True).order("id").execute()
        return r.data if r.data else DEFAULT_ACTIVITIES
    except Exception as e:
        logger.warning(f"load_activities failed, using defaults: {e}")
        return DEFAULT_ACTIVITIES

# ============================================================
# PLOT TYPES WITH BOX MATH (C Merged)
# ============================================================
# Note: Keeping dictionary keys exactly as provided to avoid breaking garden.py/meeting.py
PLOT_TYPES = {
    "A ": {"area": 3.0, "colour": "#2ca02c", "total": 16, "boxes": 12, "box_size_cm": 50},
    "B ": {"area": 2.5, "colour": "#ff7f0e", "total": 24, "boxes": 10, "box_size_cm": 50},
    "C ": {"area": 2.0, "colour": "#339af0", "total": 36, "boxes": 8, "box_size_cm": 50},
}

TOTAL_PLOTS = 76

TYPE_MAP = {
    1: "B ", 2: "B ", 3: "C ", 4: "C ", 5: "A ", 6: "B ", 7: "A ", 8: "C ", 9: "C ", 10: "B ",
    11: "B ", 12: "C ", 13: "C ", 14: "A ", 15: "B ", 16: "A ", 17: "C ", 18: "C ", 19: "B ", 20: "B ",
    21: "C ", 22: "C ", 23: "A ", 24: "B ", 25: "A ", 26: "C ", 27: "C ", 28: "B ", 29: "B ", 30: "C ",
    31: "A ", 32: "B ", 33: "C ", 34: "B ", 35: "A ", 36: "B ", 37: "B ", 38: "B ", 39: "B ", 40: "B ",
    41: "C ", 42: "C ", 43: "A ", 44: "B ", 45: "A ", 46: "C ", 47: "C ", 48: "B ", 49: "B ", 50: "C ",
    51: "C ", 52: "A ", 53: "B ", 54: "A ", 55: "C ", 56: "C ", 57: "B ", 58: "B ", 59: "C ", 60: "C ",
    61: "A ", 62: "B ", 63: "A ", 64: "C ", 65: "C ", 66: "B ", 67: "B ", 68: "C ", 69: "B ", 70: "A ",
    71: "C ", 72: "B ", 73: "B ", 74: "A ", 75: "B ", 76: "B "
}

# ========== MOBILE CSS ==========
MOBILE_CSS = """
<style>
/* Force viewport on mobile */
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
    .stButton >button{
        width:100%!important;
        font-size:15px!important;
        padding:14px!important;
        min-height:48px!important;
        border-radius:8px!important;
        margin:4px 0!important;
    }
    .stTextInput >div >div >input,
    .stNumberInput >div >div >input,
    .stSelectbox >div >div >select,
    .stTextArea >div >div >textarea{
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
</style>
"""