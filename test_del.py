import os
from supabase import create_client

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = os.environ.get('SUPABASE_KEY')
if not key:
    print("NO KEY")
    exit()

supabase = create_client(url, key)

# Let's list the clients that have "ТЕСТ" in their name
res = supabase.table("clients").select("*").ilike("name", "%ТЕСТ%").execute()
print(f"Found {len(res.data)} clients with 'ТЕСТ'")
for c in res.data:
    print(c)

# Ask to delete? We will just delete them since the user requested it.
if res.data:
    for c in res.data:
        del_res = supabase.table("clients").delete().eq("id", c["id"]).execute()
        print(f"Deleted {c['name']} - Response: {del_res.data}")
