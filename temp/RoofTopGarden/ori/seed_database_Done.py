# seed_database.py - Initialize Supabase with 76 plots
from supabase import create_client

SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

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

PLOT_TYPES = {
    "A": 3.0, "B": 2.5, "C": 2.25, "D": 2.0
}

def seed_database():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("Seeding garden_plots table...")
    
    plots = []
    for plot_num in range(1, 77):
        plot_type = TYPE_MAP[plot_num]
        area = PLOT_TYPES[plot_type]
        
        plots.append({
            "plot_number": plot_num,
            "plot_type": plot_type,
            "area": area,
            "occupied": False,
            "user_id": None,
            "user_name": None,
            "contact": None,
            "change_log": "Initial seed"
        })
    
    # Insert in batches of 20
    for i in range(0, len(plots), 20):
        batch = plots[i:i+20]
        try:
            result = supabase.table('garden_plots').insert(batch).execute()
            print(f"Inserted plots {i+1} to {i+len(batch)}")
        except Exception as e:
            print(f"Error inserting batch: {e}")
            # Try individual inserts if batch fails
            for plot in batch:
                try:
                    supabase.table('garden_plots').insert(plot).execute()
                except:
                    print(f"Failed to insert plot {plot['plot_number']} (may already exist)")
    
    print("✅ Database seeded! Check Supabase dashboard to verify.")

if __name__ == "__main__":
    seed_database()