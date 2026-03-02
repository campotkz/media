import sys
import os
import json
import pandas as pd
import io
from datetime import datetime
from supabase import create_client, Client

# Add parent dir to path to import config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock environment for testing
SUPABASE_URL = "https://your-proj.supabase.co" # Need to get real ones from env or file
SUPABASE_KEY = "your-key"

# Try to load from api/index.py or env
try:
    with open('api/index.py', 'r', encoding='utf-8') as f:
        content = f.read()
        import re
        url_match = re.search(r'SUPABASE_URL\s*=\s*(?:"|\')(.*?)(?:"|\')', content)
        key_match = re.search(r'SUPABASE_KEY\s*=\s*(?:"|\')(.*?)(?:"|\')', content)
        if url_match: SUPABASE_URL = url_match.group(1)
        if key_match: SUPABASE_KEY = key_match.group(1)
except: pass

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_test_report(shift_id):
    print(f"Testing report for shift: {shift_id}")
    
    # 1. Fetch Data
    s_res = supabase.table('production_shifts').select("*").eq('id', shift_id).execute()
    if not s_res.data:
        print("Shift not found")
        return
    shift = s_res.data[0]
    print("Shift data loaded")

    l_res = supabase.table('production_logs').select("*").eq('shift_id', shift_id).order('event_time').execute()
    logs = l_res.data
    if not logs:
        print("No logs found")
        return
    print(f"Logs loaded: {len(logs)}")

    df_logs = pd.DataFrame(logs)
    print("Converting timestamps...")
    try:
        # Check if naive or aware
        times = pd.to_datetime(df_logs['event_time'])
        if times.dt.tz is None:
            print("Detected naive timestamps, localizing to UTC first")
            df_logs['time'] = times.dt.tz_localize('UTC').dt.tz_convert('Asia/Almaty')
        else:
            print("Detected aware timestamps, converting to Almaty")
            df_logs['time'] = times.dt.tz_convert('Asia/Almaty')
        print("Timestamps converted successfully")
    except Exception as e:
        print(f"Timestamp conversion ERROR: {e}")
        return

    # 2. Create Excel
    print("Building Excel...")
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main protocol
            protocol = []
            plan = json.loads(shift.get('schedule', '[]'))
            if not isinstance(plan, list): plan = []
            
            for i, p_row in enumerate(plan):
                num = p_row.get('num', '')
                task_name = p_row.get('task', p_row.get('notes', '—'))
                planned_time = f"{p_row.get('start','--:--')}—{p_row.get('end','--:--')}"
                actual_start = "—"
                
                # Filter logs for this row
                row_logs = df_logs[df_logs['data'].apply(lambda x: (x.get('plan_row') or {}).get('num') == num if num else False)]
                if not row_logs.empty:
                    actual_start = row_logs.iloc[0]['time'].strftime('%H:%M')
                
                protocol.append({'№': num or i+1, 'Task': task_name, 'Plan': planned_time, 'Actual': actual_start})
            
            pd.DataFrame(protocol).to_excel(writer, sheet_name='PROT', index=False)
            print("Excel sheets added")
        
        print("Excel Buffer created successfully")
    except Exception as e:
        print(f"Excel building ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Get last shift id
    res = supabase.table('production_shifts').select("id").order("start_time", desc=True).limit(1).execute()
    if res.data:
        test_report(res.data[0]['id'])
    else:
        print("No shifts found in DB")
