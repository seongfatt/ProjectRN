import requests
import time
from datetime import datetime

APP_URL = "https://woodlands-community-hub.onrender.com"

def keep_server_awake():
    """Ping the server every 10 minutes to prevent sleep"""
    print(f"Starting keep-alive service at {datetime.now()}")
    print(f"Pinging {APP_URL} every 10 minutes...")
    
    while True:
        try:
            response = requests.get(APP_URL, timeout=10)
            print(f"[{datetime.now()}] Ping successful - Status: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now()}] Ping failed: {e}")
        
        # Wait 10 minutes (Render sleeps after 15 minutes)
        time.sleep(600)  # 10 minutes

if __name__ == "__main__":
    keep_server_awake()