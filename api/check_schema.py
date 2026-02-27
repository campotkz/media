import os
from supabase import create_client

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
sb = create_client(url, key)

try:
    # Try to insert a row with string project_id and see the error or check columns
    # Actually, let's use a query to check column types if possible via RPC or just trial and error
    print("Testing production_shifts schema...")
    res = sb.table('production_shifts').select('*').limit(1).execute()
    print("Columns in production_shifts:", res.data[0].keys() if res.data else "Table empty")
    
    # Check specifically for project_id type by trying to filter with a number vs string
    try:
        sb.table('production_shifts').select('id').eq('project_id', 'testing_string').execute()
        print("✅ project_id accepts strings")
    except Exception as e:
        print(f"❌ project_id error: {e}")

    try:
        # Check chat_id
        sb.table('production_shifts').select('id').eq('chat_id', '123456789').execute()
        print("✅ chat_id accepts strings")
    except Exception as e:
        print(f"❌ chat_id error: {e}")

except Exception as e:
    print(f"General error: {e}")
