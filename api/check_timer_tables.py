"""Check if production_shifts and production_logs tables exist in Supabase"""
import os
from supabase import create_client

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
sb = create_client(url, key)

print("=" * 50)
print("CHECKING TIMER TABLES IN SUPABASE")
print("=" * 50)

# 1. Check production_shifts
print("\n--- production_shifts ---")
try:
    res = sb.table('production_shifts').select('*').limit(5).execute()
    print(f"✅ Table EXISTS. Rows found: {len(res.data)}")
    if res.data:
        for r in res.data:
            print(f"   ID: {r.get('id')}, Project: {r.get('project_id')}, Status: {r.get('status')}, Start: {r.get('start_time')}")
    else:
        print("   (empty table - no shifts recorded yet)")
except Exception as e:
    print(f"❌ ERROR: {e}")

# 2. Check production_logs
print("\n--- production_logs ---")
try:
    res = sb.table('production_logs').select('*').limit(10).execute()
    print(f"✅ Table EXISTS. Rows found: {len(res.data)}")
    if res.data:
        for r in res.data:
            print(f"   Type: {r.get('event_type')}, Shift: {r.get('shift_id')}, Data: {r.get('data')}")
    else:
        print("   (empty table - no events logged yet)")
except Exception as e:
    print(f"❌ ERROR: {e}")

# 3. Check shoots table has gear column
print("\n--- shoots (gear column check) ---")
try:
    res = sb.table('shoots').select('id, project, location, gear, schedule').limit(3).execute()
    print(f"✅ Table EXISTS. Sample rows: {len(res.data)}")
    if res.data:
        for r in res.data:
            has_gear = "YES" if r.get('gear') else "no"
            has_sched = "YES" if r.get('schedule') else "no"
            print(f"   Project: {r.get('project')}, Location: {r.get('location')}, gear: {has_gear}, schedule: {has_sched}")
except Exception as e:
    print(f"❌ ERROR: {e}")

# 4. Test INSERT into production_shifts (dry run check)
print("\n--- INSERT test (production_shifts) ---")
try:
    res = sb.table('production_shifts').insert({
        'project_id': 'test_diag',
        'status': 'test',
        'start_time': '2026-01-01T00:00:00Z'
    }).execute()
    if res.data:
        test_id = res.data[0]['id']
        print(f"✅ INSERT works! Test row ID: {test_id}")
        # Clean up
        sb.table('production_shifts').delete().eq('id', test_id).execute()
        print(f"   (cleaned up test row)")
    else:
        print(f"⚠️ INSERT returned no data (possible RLS block)")
except Exception as e:
    print(f"❌ INSERT FAILED: {e}")

# 5. Test INSERT into production_logs
print("\n--- INSERT test (production_logs) ---")
try:
    res = sb.table('production_logs').insert({
        'shift_id': '00000000-0000-0000-0000-000000000000',
        'event_type': 'test_diag',
        'data': {'test': True}
    }).execute()
    if res.data:
        test_id = res.data[0]['id']
        print(f"✅ INSERT works! Test row ID: {test_id}")
        sb.table('production_logs').delete().eq('id', test_id).execute()
        print(f"   (cleaned up test row)")
    else:
        print(f"⚠️ INSERT returned no data (possible RLS block)")
except Exception as e:
    print(f"❌ INSERT FAILED: {e}")

print("\n" + "=" * 50)
print("DONE")
