import os
from supabase import create_client

url = "https://waekzofajzqcpoeldhkt.supabase.co"
key = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V"
sb = create_client(url, key)

res = sb.table('clients').select('name, chat_id, thread_id').eq('category', 'casting').execute()
print(res.data)
