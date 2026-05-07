import os
from supabase import create_client

def diag():
    url = "https://waekzofajzqcpoeldhkt.supabase.co"
    # Using the key found in check_db.py as a fallback
    key = os.environ.get("SUPABASE_KEY") or "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
    
    print(f"Connecting to {url}...")
    try:
        supabase = create_client(url, key)
        
        tables = [
            "clients", "shoots", "team", "contacts", 
            "production_shifts", "tasks", "casting_applications"
        ]
        
        print("Table counts:")
        for table in tables:
            try:
                # Use a simple select to check if table is reachable and empty
                res = supabase.table(table).select("id").limit(1).execute()
                count = len(res.data)
                print(f" - {table:20}: {count} rows (first 1)")
            except Exception as e:
                print(f" - {table:20}: ERROR - {str(e)[:50]}")
                
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    diag()
