import os
from supabase import create_client

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"

sb = create_client(url, key)

res = sb.table('casting_applications').select('id, full_name, casting_target, chat_id, thread_id, tg_message_id').order('created_at', desc=True).limit(10).execute()
for r in res.data:
    print(r)
