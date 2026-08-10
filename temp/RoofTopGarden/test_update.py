from supabase import create_client
from datetime import datetime, timezone

supabase = create_client(
    "https://nqmvsjubgsghjpzojaxm.supabase.co",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

)

res = supabase.table("garden_plots").update({
    "occupied": True,
    "user_id": "TEST",
    "user_name": "Debug User test",
    "contact": "99999999",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
}).eq("plot_number", 5).execute()

# Test request creation
req_res = supabase.table("plot_requests").insert({
    "plot_number": 9,
    "user_id": "TEST_USER",
    "user_name": "Test Creator",
    "contact": "12345678",
    "notes": "Test request",
    "status": "pending"
}).execute()

print("Request created:", req_res.data)

print("Response:", res.data)