import requests
import json

SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" 

def main():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/clients"
    
    print(f"Requesting: {url}")
    r = requests.get(url, headers=headers)
    
    if r.status_code == 200:
        data = r.json()
        print(f"Found {len(data)} records total:")
        for row in data:
            print(f"- ID: {row['id']}, CID: {row['chat_id']}, TID: {row['thread_id']}, Name: {row['name']}")
    else:
        print(f"Error {r.status_code}: {r.text}")

    # TEST UPDATE: Try to update the row we just inserted (ID 32)
    print("\n--- TEST UPDATE ON NEW RECORD (ID 32) ---")
    url_upd = f"{SUPABASE_URL}/rest/v1/clients?id=eq.32"
    headers_upd = headers.copy()
    headers_upd["Prefer"] = "return=representation"
    
    payload = {"is_hidden": True}
    
    print(f"Updating ID 32 via: {url_upd}")
    r_u = requests.patch(url_upd, headers=headers_upd, data=json.dumps(payload))
    
    if r_u.status_code in [200, 201, 204]:
        print("✅ New Record Update SUCCESS")
        print(f"Response: {r_u.text}")
    else:
        print(f"❌ New Record Update FAILED {r_u.status_code}: {r_u.text}")

if __name__ == "__main__":
    main()
