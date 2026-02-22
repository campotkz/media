import os
from supabase import create_client, Client
from datetime import datetime

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
supabase: Client = create_client(url, key)

today = datetime.now().strftime('%Y-%m-%d')
print(f"Checking shoots for: {today}")

res = supabase.table('shoots').select('*').eq('date', today).execute()
if res.data:
    print(f"Found {len(res.data)} shoots:")
    for s in res.data:
        print(f"- ID: {s['id']}, Project: {s['project']}, Location: {s['location']}")
else:
    print("No shoots found for today.")
