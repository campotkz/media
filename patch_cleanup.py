import re

with open('api/index.py', 'r') as f:
    content = f.read()

old_topic_deleted = """@bot.message_handler(content_types=['forum_topic_deleted'])
def handle_topic_deleted(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if tid:
            # Delete project from clients
            supabase.from_("clients").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            # Also delete related contacts? (Optional but clean)
            # supabase.from_("contacts").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            print(f"🗑️ DELETED: Project from topic {tid} in chat {cid} removed from DB.")
    except Exception as e: print(f"❌ Topic Deleted Err: {e}")"""

new_topic_deleted = """@bot.message_handler(content_types=['forum_topic_deleted'])
def handle_topic_deleted(message):
    try:
        cid = message.chat.id
        # IMPORTANT: The message_thread_id might not be the same as the deleted topic ID in all cases.
        # However, for forum_topic_deleted, it IS the thread_id of the topic being deleted.
        tid = message.message_thread_id

        if tid:
            # Check if it exists before deleting (for logging)
            p_res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
            if p_res.data:
                p_name = p_res.data[0]['name']
                # Delete project from clients
                supabase.from_("clients").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
                print(f"🗑️ DELETED: Project '{p_name}' (Topic {tid}) removed from DB.")

                # We can also clean up contacts related to this project
                supabase.from_("contacts").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            else:
                print(f"⚠️ DELETED TOPIC: Topic {tid} deleted, but no corresponding project found in DB.")
    except Exception as e: print(f"❌ Topic Deleted Err: {e}")"""

content = content.replace(old_topic_deleted, new_topic_deleted)

with open('api/index.py', 'w') as f:
    f.write(content)
