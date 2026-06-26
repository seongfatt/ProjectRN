import streamlit as st
from supabase import create_client
import os

# ========== DATABASE CONFIG ==========
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

# ========== APP URL - UPDATE THIS! ==========
# Local development: "http://localhost:8501"
# Hugging Face: "https://wrnz6-community-hub.hf.space"
APP_URL = os.getenv("APP_URL", "https://wrnz6-community-hub.hf.space")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
CHECKER_PASSWORD = os.getenv("CHECKER_PASSWORD", "checker123")

@st.cache_resource
def get_db():
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        client.table('participants').select("id").limit(1).execute()
        return client, True
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None, False

supabase, DB_CONNECTED = get_db()

def refresh_data():
    st.cache_data.clear()
    st.cache_resource.clear()

DEFAULT_ACTIVITIES = [
    {"id": 1, "name": "Cardio Drumming", "session_1_label": "Session 1 (7PM-8PM)", "session_2_label": "Session 2 (8PM-9PM)", "active": True},
]

def load_activities():
    if not DB_CONNECTED: return DEFAULT_ACTIVITIES
    try:
        r = supabase.table('activities').select("*").eq('active', True).order('id').execute()
        return r.data if r.data else DEFAULT_ACTIVITIES
    except:
        return DEFAULT_ACTIVITIES

PLOT_TYPES = {
    "A": {"area": 3.0, "colour": "#2ca02c", "total": 16},
    "B": {"area": 2.5, "colour": "#ff7f0e", "total": 24},
    "C": {"area": 2.25, "colour": "#1f77b4", "total": 8},
    "D": {"area": 2.0, "colour": "#d62728", "total": 28},
}
TOTAL_PLOTS = 76

TYPE_MAP = {1:"B",2:"B",3:"D",4:"D",5:"A",6:"B",7:"A",8:"D",9:"D",10:"B",
    11:"B",12:"D",13:"D",14:"A",15:"B",16:"A",17:"D",18:"D",19:"B",20:"B",
    21:"D",22:"D",23:"A",24:"B",25:"A",26:"D",27:"D",28:"B",29:"B",30:"D",
    31:"A",32:"C",33:"D",34:"B",35:"A",36:"C",37:"C",38:"C",39:"B",40:"B",
    41:"D",42:"D",43:"A",44:"B",45:"A",46:"D",47:"D",48:"B",49:"B",50:"D",
    51:"D",52:"A",53:"B",54:"A",55:"D",56:"D",57:"B",58:"B",59:"D",60:"D",
    61:"A",62:"B",63:"A",64:"D",65:"D",66:"B",67:"B",68:"D",69:"C",70:"A",
    71:"D",72:"B",73:"C",74:"A",75:"C",76:"C"}

MOBILE_CSS = """<style>
/* Force viewport on mobile */
@media(max-width:768px){
    body{min-width:100vw!important; max-width:100vw!important; overflow-x:hidden!important;}
    .main .block-container{padding:0.3rem!important; max-width:100vw!important; width:100vw!important;}

    /* Hide sidebar completely on mobile */
    [data-testid="stSidebar"]{display:none!important;}
    [data-testid="stSidebarCollapseButton"]{display:none!important;}
    [data-testid="collapsedControl"]{display:none!important;}

    /* Full width everything */
    .element-container{width:100%!important; max-width:100%!important;}
    .stMarkdown{width:100%!important;}

    /* Headers */
    h1{font-size:17px!important; margin:4px 0!important;}
    h2{font-size:15px!important; margin:3px 0!important;}
    h3{font-size:13px!important;}
    p, li{font-size:13px!important; line-height:1.4!important;}

    /* Buttons full width and big */
    .stButton>button{
        width:100%!important;
        font-size:15px!important;
        padding:14px!important;
        min-height:48px!important;
        border-radius:8px!important;
        margin:4px 0!important;
    }

    /* Inputs */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select,
    .stTextArea>div>div>textarea{
        font-size:16px!important;
        padding:12px!important;
        min-height:48px!important;
    }

    /* Radio buttons vertical */
    .stRadio [role="radiogroup"]{flex-direction:column!important;}
    .stRadio [role="radiogroup"] label{margin:3px 0!important; padding:6px!important;}

    /* Tabs scrollable */
    .stTabs [data-baseweb="tab-list"]{overflow-x:auto!important; flex-wrap:nowrap!important;}
    .stTabs [data-baseweb="tab-list"] button{font-size:11px!important; padding:6px 8px!important; white-space:nowrap!important;}

    /* Columns stack */
    .stColumns{flex-direction:column!important;}
    .stColumns > div{width:100%!important; flex:none!important; max-width:100%!important; margin:2px 0!important;}

    /* Metrics */
    .stMetric{padding:4px!important;}
    .stMetric label{font-size:10px!important;}
    .stMetric .css-1xarl3l{font-size:16px!important;}

    /* Dataframes */
    .stDataFrame{font-size:11px!important;}
    .stDataFrame > div{overflow-x:auto!important;}

    /* Images */
    img{max-width:100%!important; height:auto!important;}

    /* Expanders */
    .streamlit-expanderHeader{font-size:13px!important; padding:10px!important;}

    /* Remove extra margins */
    .main > div{padding-left:0!important; padding-right:0!important;}
}

/* PDPA notice */
.pdpa-notice{background:#fff3cd;border-left:4px solid #ffc107;padding:10px;border-radius:4px;margin:8px 0;font-size:13px;}
</style>"""
