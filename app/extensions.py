from flask_apscheduler import APScheduler
from supabase import create_client, Client
import os

# Scheduler Instance
scheduler = APScheduler()

# Supabase Client (Lazy load to prevent import errors)
supabase: Client = None


def init_supabase(app):
    global supabase
    url = app.config.get("SUPABASE_URL")
    key = app.config.get("SUPABASE_KEY")
    if url and key:
        try:
            supabase = create_client(url, key)
            print(f"Supabase initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Supabase: {e}")
    else:
        print("Supabase credentials not found. Skipping initialization.")


def get_supabase_config():
    """Get Supabase config for frontend."""
    return {
        "url": os.getenv("SUPABASE_URL"),
        "anon_key": os.getenv("SUPABASE_ANON_KEY"),
    }
