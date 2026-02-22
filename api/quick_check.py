import os
from supabase import create_client, Client

SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    # Try to fetch one row to see columns
    res = supabase.table("casting_applications").select("*").limit(1).execute()
    if res.data:
        print("Columns found:", res.data[0].keys())
    else:
        print("Empty table, trying to guess columns via select")
        # Just try to see if selecting the new columns fails
        try:
            supabase.table("casting_applications").select("tg_message_id, additional_media").limit(1).execute()
            print("SUCCESS: Columns tg_message_id and additional_media EXIST.")
        except Exception as e:
            print(f"ERROR: Columns might be missing: {e}")
except Exception as e:
    print(f"Global Error: {e}")
