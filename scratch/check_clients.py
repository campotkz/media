import os
from supabase import create_client, Client

SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    res = supabase.from_("clients").select("*").execute()
    print(f"Total records in 'clients': {len(res.data)}")
    for row in res.data:
        print(f"ID: {row.get('id')}, Name: {row.get('name')}, ChatID: {row.get('chat_id')}, ThreadID: {row.get('thread_id')}")
except Exception as e:
    print(f"Error: {e}")
