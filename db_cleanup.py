import requests
import json
import os

SUPABASE_PAT = os.environ.get('SUPABASE_PAT')
PROJECT_REF = "waekzofajzqcpoeldhkt"

def run_query(sql):
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/query"
    headers = {"Authorization": f"Bearer {SUPABASE_PAT}", "Content-Type": "application/json"}
    payload = {"query": sql}
    resp = requests.post(url, json=payload, headers=headers)
    print(resp.text)

run_query("DELETE FROM public.clients WHERE name ILIKE '%ТЕСТ%' OR name ILIKE '%TECT%';")
