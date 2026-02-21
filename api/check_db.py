import os
from supabase import create_client

SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check():
    print("--- TEAM ---")
    res = supabase.from_("team").select("*").execute()
    for row in res.data:
        print(row)
        
    print("\n--- CLIENTS (Active Topics) ---")
    res = supabase.from_("clients").select("*").not_.is_("thread_id", "null").execute()
    for row in res.data:
        print(row)
        
    print("\n--- CONTACTS ---")
    res = supabase.from_("contacts").select("*").execute()
    for row in res.data:
        print(row)

if __name__ == "__main__":
    check()
