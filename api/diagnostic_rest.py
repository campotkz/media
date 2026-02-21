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
    
    target_cid = -1003738942785
    url = f"{SUPABASE_URL}/rest/v1/clients?chat_id=eq.{target_cid}"
    
    print(f"Requesting: {url}")
    r = requests.get(url, headers=headers)
    
    if r.status_code == 200:
        data = r.json()
        print(f"Found {len(data)} records:")
        for row in data:
            print(json.dumps(row, indent=2))
    else:
        print(f"Error {r.status_code}: {r.text}")

if __name__ == "__main__":
    main()
