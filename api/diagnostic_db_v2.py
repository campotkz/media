from supabase import create_client
import json

SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" 

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Check for the specific chat reported by the user
    target_cid = -1003738942785
    print(f"Checking projects for chat_id: {target_cid}")
    
    res = supabase.from_("clients").select("*").eq("chat_id", target_cid).execute()
    
    if res.data:
        print(f"Found {len(res.data)} records:")
        for row in res.data:
            print(f"ID: {row.get('id')} | Thread: {row.get('thread_id')} | Name: {row.get('name')} | Hidden: {row.get('is_hidden')} | Active: {row.get('is_active')}")
    else:
        print("No records found for this chat_id.")

if __name__ == "__main__":
    main()
