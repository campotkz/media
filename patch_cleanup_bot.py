import re

with open('api/index.py', 'r') as f:
    content = f.read()

new_command = """@bot.message_handler(commands=['del_project'])
def handle_del_project(message):
    try:
        # Only allow if there's a name provided
        args = message.text.replace('/del_project', '').strip()
        if not args:
            bot.reply_to(message, "❌ Укажите точное название проекта для удаления. Пример: `/del_project ТЕСТОВЫЙ`", parse_mode="Markdown")
            return

        cid = message.chat.id

        # Search for project by name in this chat
        res = supabase.from_("clients").select("id, name, thread_id").eq("chat_id", cid).ilike("name", args).execute()

        if not res.data:
            bot.reply_to(message, f"❌ Проект с именем '{args}' не найден.")
            return

        deleted_count = 0
        for p in res.data:
            pid = p['id']
            tid = p['thread_id']
            pname = p['name']

            # Delete project
            supabase.from_("clients").delete().eq("id", pid).execute()

            # Delete related contacts
            if tid:
                supabase.from_("contacts").delete().eq("chat_id", cid).eq("thread_id", tid).execute()

            deleted_count += 1

        bot.reply_to(message, f"🗑️ Успешно удалено проектов: {deleted_count}.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка удаления проекта: {e}")

"""

# Insert before 'def ensure_project'
content = content.replace("def ensure_project(", new_command + "def ensure_project(")

with open('api/index.py', 'w') as f:
    f.write(content)
