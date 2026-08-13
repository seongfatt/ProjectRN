# sync_db.py
import csv
from supabase import create_client, Client

# 🔥 Your Supabase Credentials (from your config.py)
SUPABASE_URL = "https://nqmvsjubgsghjpzojaxm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbXZzanViZ3NnaGpwem9qYXhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NzQ3ODMsImV4cCI6MjA4NTE1MDc4M30.OukUcFvR1J5-DJVoPGmgjf34dBv7lrB1198YCp_uRIw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync():
    print("🔄 [1/2] Updating Participants (Member Types)...")
    with open('2026-08-10T09-27_export.csv', mode='r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            pid = row['ID']
            mtype = row['Member Type']
            try:
                supabase.table('participants').update({'member_type': mtype}).eq('id', pid).execute()
                print(f"  ✅ {row['Name']} -> {mtype}")
            except Exception as e:
                print(f"  ❌ Error {pid}: {e}")

    print("\n🔄 [2/2] Updating Garden Plots...")
    with open('2026-08-10T09-29_export_garden plot.csv', mode='r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            pnum = int(row['Plot Number'])
            updates = {
                'plot_type': row['Plot Type'],
                'occupied': row['Status'] == '[OCCUPIED]',
                'user_id': row['Owner ID'] if row['Owner ID'] else None,
                'user_name': row['Owner Name'] if row['Owner Name'] else None,
                'contact': row['Contact'] if row['Contact'] else None,
                'paid': row['Paid'] == 'Yes'
            }
            try:
                supabase.table('garden_plots').update(updates).eq('plot_number', pnum).execute()
                print(f"  ✅ Plot {pnum} -> {row['Status']} ({row['Paid']})")
            except Exception as e:
                print(f"  ❌ Error Plot {pnum}: {e}")
                
    print("\n🎉 Sync Complete! Your Supabase database is now fully organized.")

if __name__ == "__main__":
    sync()