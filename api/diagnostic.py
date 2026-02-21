import os
from supabase import create_client

URL = "https://waekzofajzqcpoeldhkt.supabase.co"
KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"

supabase = create_client(URL, KEY)

print("--- TEAM ---")
team = supabase.table("team").select("*").execute()
for t in team.data:
    print(f"ID: {t['id']}, T_ID: {t.get('telegram_id')}, Name: {t.get('full_name')}, Pos: {t.get('position')}")

print("\n--- CLIENTS ---")
clients = supabase.table("clients").select("*").execute()
for c in clients.data:
    print(f"ID: {c['id']}, Name: {c['name']}, Thread: {c.get('thread_id')}")

print("\n--- CONTACTS ---")
contacts = supabase.table("contacts").select("*").execute()
for ct in contacts.data:
    print(f"ID: {ct['id']}, Name: {ct['name']}, Phone: {ct['phone']}, Thread: {ct.get('thread_id')}")
