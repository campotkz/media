import os
from supabase import create_client

S_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
S_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" # I should use the admin key if possible but I only have the public one in the code above.
# Wait, I saw a service role key in another file? No, it's usually SB_SERVICE_KEY env var.
# Let's try to use the public client for viewing.

supabase = create_client(S_URL, S_KEY)

cid = -1003738942785 # From screenshot
print(f"Checking projects for chat_id: {cid}")

res = supabase.from_("clients").select("*").eq("chat_id", cid).execute()
if res.data:
    print(f"Found {len(res.data)} projects:")
    for p in res.data:
        print(f" - ID: {p['id']}, TID: {p['thread_id']}, Name: {p['name']}, Hidden: {p['is_hidden']}, Active: {p['is_active']}")
else:
    print("No projects found for this chat_id.")

# Check all hidden projects
print("\nChecking ALL hidden projects in DB:")
res_h = supabase.from_("clients").select("*").eq("is_hidden", True).execute()
if res_h.data:
    for p in res_h.data:
        print(f" - CID: {p['chat_id']}, TID: {p['thread_id']}, Name: {p['name']}")
else:
    print("No hidden projects found.")
