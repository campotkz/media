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
            print(f"- CID: {row['chat_id']}, TID: {row['thread_id']}, Name: {row['name']}, Hidden: {row['is_hidden']}, Active: {row['is_active']}")
    else:
        print(f"Error {r.status_code}: {r.text}")

    # Also check hidden
    url_h = f"{SUPABASE_URL}/rest/v1/clients?is_hidden=eq.true"
    print(f"\nRequesting hidden: {url_h}")
    r_h = requests.get(url_h, headers=headers)
    if r_h.status_code == 200:
        data_h = r_h.json()
        print(f"Found {len(data_h)} hidden records:")
        for row in data_h:
            print(f"- CID: {row['chat_id']}, TID: {row['thread_id']}, Name: {row['name']}")
    else:
         print(f"Error {r_h.status_code}: {r_h.text}")

if __name__ == "__main__":
    main()
