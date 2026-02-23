import os
import telebot
import re
from telebot import types
from flask import Flask, request, jsonify
from supabase import create_client, Client
import pandas as pd
import base64
import io
import json
from datetime import datetime

# Config
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" 
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Version indicator for debugging
VERSION = "1.5.2" 

@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            print(f"Webhook Error: {e}")
        return ''
    return 'Forbidden', 403

@app.route('/api/report', methods=['POST', 'OPTIONS'])
def submit_report():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        data = request.json or {}
        chat_id, thread_id = data.get('chat_id'), data.get('thread_id')
        if not chat_id: return jsonify({'error': 'No chat_id'}), 400
        prev = supabase.table('client_feedback').select('leads_count, sales_count').eq('thread_id', thread_id or 0).order('created_at', desc=True).limit(2).execute()
        pl, ps = (prev.data[1]['leads_count'] or 0, prev.data[1]['sales_count'] or 0) if len(prev.data) > 1 else (0, 0)
        cl, cs = int(data.get('leads_count', 0)), int(data.get('sales_count', 0))
        def v(k): return str(data.get(k)) if data.get(k) else "-"
        msg = f"📊 **ОТЧЕТ ЗА МЕСЯЦ**\n\n👤 Имя: {v('client_name')}\nInst: {v('instagram')}\n\n🔥 Лиды: {cl} ({cl-pl:+})\nПродажи: {cs} ({cs-ps:+})"
        bot.send_message(chat_id, msg, message_thread_id=thread_id, parse_mode="Markdown")
        r = jsonify({'status': 'ok'})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r
    except Exception as e:
        r = jsonify({'error': str(e)}); r.headers.add('Access-Control-Allow-Origin', '*'); return r, 500

@app.route('/api/send_excel', methods=['POST', 'OPTIONS'])
def send_excel():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        data = request.json or {}
        project_name = data.get('project_name')
        filename = data.get('filename', 'Shoot_Export.xlsx')
        base64_data = data.get('base64_data')

        if not project_name or not base64_data:
            return jsonify({'error': 'Missing project_name or base64_data'}), 400

        # Find target chat/thread from database
        res = supabase.from_("clients").select("chat_id, thread_id").eq("name", project_name).execute()
        if not res.data:
            return jsonify({'error': f'Project "{project_name}" not found in database'}), 404
        
        target = res.data[0]
        chat_id = target.get('chat_id')
        thread_id = target.get('thread_id')

        if not chat_id:
            return jsonify({'error': f'Project "{project_name}" has no linked chat_id'}), 400

        # Decode base64 file
        file_bytes = base64.b64decode(base64_data)
        file_io = io.BytesIO(file_bytes)
        file_io.name = filename

        # Send to Telegram
        bot.send_document(chat_id, file_io, message_thread_id=thread_id)

        r = jsonify({'status': 'ok', 'message': f'File sent to {project_name}'})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r
    except Exception as e:
        r = jsonify({'error': str(e)})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r, 500

@bot.message_handler(commands=['start', 'cal'])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", url=APP_URL))
    bot.send_message(message.chat.id, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=message.message_thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def handle_status(message):
    try:
        user = message.from_user
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        pos = res.data[0].get('position') if res.data else "не зарегистрирован"
        bot.reply_to(message, f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `{user.first_name}`\nID: `{user.id}`\nPosition: `{pos}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Status Error: {e}")

@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    cid, tid = message.chat.id, message.message_thread_id or ""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=f"{APP_URL}feedback.html?cid={cid}&tid={tid}"))
    bot.send_message(cid, f"📉 **СВЕРКА МЕТРИК**\n\n`{APP_URL}feedback.html?cid={cid}&tid={tid}`", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Goldy | Luxury`", parse_mode="Markdown")
            return
        
        # Determine category from chat title (group name)
        chat_title = message.chat.title or ""
        category = 'casting' if 'КАСТИНГ' in chat_title.upper() else 'media'
        
        # 1. Update existing
        res = supabase.from_("clients").update({"name": new_name, "category": category}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. If no rows updated, create it with the correct name and category
        if not res.data:
            ensure_project(cid, tid, chat_title, forced_name=new_name)
            bot.reply_to(message, f"✅ Проект создан и назван: **{new_name}**")
        else:
            bot.reply_to(message, f"✅ Проект переименован: **{new_name}**")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}")

@bot.message_handler(commands=['archive'])
def handle_archive(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return
        
        # 1. Try exact match
        res = supabase.from_("clients").update({"is_hidden": True, "is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. Try match by tid where chat_id is null (legacy cleanup)
        if not res.data:
            res = supabase.from_("clients").update({"is_hidden": True, "is_active": False, "chat_id": cid}).is_("chat_id", "null").eq("thread_id", tid).execute()
        
        if res.data:
            bot.reply_to(message, "🗄️ **АРХИВИРОВАНО**\nЭтот топик скрыт из всех списков выбора на сайте.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден в базе данных. Попробуйте сначала создать ссылку командой `/cast_link` или просто подождать.", parse_mode="Markdown")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка архивации: {e}")

@bot.message_handler(commands=['unarchive'])
def handle_unarchive(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return
            
        # 1. Try exact match
        res = supabase.from_("clients").update({"is_hidden": False, "is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. Try match by tid where chat_id is null
        if not res.data:
            res = supabase.from_("clients").update({"is_hidden": False, "is_active": True, "chat_id": cid}).is_("chat_id", "null").eq("thread_id", tid).execute()

        if res.data:
            bot.reply_to(message, "🔓 **РАЗАРХИВИРОВАНО**\nТопик снова доступен в списках выбора.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден.", parse_mode="Markdown")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка разархивации: {e}")

@bot.message_handler(commands=['cast_link'])
def handle_cast_link(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        # 1. Ensure project exists in DB
        ensure_project(cid, tid, message.chat.title)
        
        # 2. Fetch the current name
        p_res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 3. If still "Project X", try to use topic name if it's better
        p_name = "Unknown Project"
        if p_res.data:
            p_name = p_res.data[0]['name']
            if p_name.startswith("Project ") and message.reply_to_message:
                # Fallback: if we only have Project ID, maybe the topic name is in the chat title?
                # Usually chat.title is the group name, not topic name.
                pass

        link = f"{APP_URL}casting.html?cid={cid}&tid={tid or ''}&proj={p_name.replace(' ', '%20')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎭 ОТКРЫТЬ АНКЕТУ", url=link))
        
        msg = f"📋 **ССЫЛКА НА АНКЕТУ**\nПроект: **{p_name}**\n\n`{link}`\n\nОтправьте эту ссылку кандидатам. Все анкеты прилетят прямо в этот чат."
        bot.send_message(cid, msg, reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка генерации ссылки: {e}")

@bot.message_handler(commands=['timer'])
def handle_timer(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return

        # 1. Ensure project exists
        ensure_project(cid, tid, message.chat.title)
        
        # 2. Get project details for the link
        p_res = supabase.from_("clients").select("id, name").eq("chat_id", cid).eq("thread_id", tid).execute()
        
        if p_res.data:
            p = p_res.data[0]
            pid = p['id']
            pname = p['name']
            
            # 3. Create TWA Keyboard
            url = f"{APP_URL}timer.html?pid={pid}&proj={pname.replace(' ', '%20')}&tid={tid or ''}&cid={cid}"
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton(text="⏱️ ЗАПУСТИТЬ ТАЙМЕР", url=url)
            markup.add(btn)
            
            bot.send_message(cid, f"🚀 **FILM TIMER PRO**\n\nПроект: **{pname}**\n\nНажмите кнопку ниже, чтобы начать замер смены.", 
                             reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден. Попробуйте написать что-нибудь в этот топик сначала.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка таймера: {e}")

@bot.message_handler(commands=['loc'])
def handle_project_location(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return

        loc_name = (message.text or "").replace('/loc', '').strip()
        if not loc_name:
            bot.reply_to(message, "📝 Напишите название локации после команды. Пример: `/loc Магазин очков №1`", parse_mode="Markdown")
            return

        # 1. Ensure project exists and get its ID
        ensure_project(cid, tid, message.chat.title)
        p_res = supabase.from_("clients").select("id, name").eq("chat_id", cid).eq("thread_id", tid).execute()
        
        if p_res.data:
            pid = p_res.data[0]['id']
            pname = p_res.data[0]['name']
            
            # 2. Upsert location
            supabase.table("project_locations").upsert({
                "project_id": pid, "name": loc_name
            }, on_conflict="project_id, name").execute()
            
            bot.reply_to(message, f"📍 Локация **{loc_name}** сохранена для проекта **{pname}**.\nТеперь она будет доступна в подсказках на сайте.")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка добавления локации: {e}")

@bot.message_handler(commands=['add'])
def handle_add(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👥 Актер", callback_data=f"add_cat:actors:{tid}"),
            types.InlineKeyboardButton("🛠 Сотрудник", callback_data=f"add_cat:crew:{tid}"),
            types.InlineKeyboardButton("🤝 Клиент", callback_data=f"add_cat:clients:{tid}"),
            types.InlineKeyboardButton("📍 Локация", callback_data=f"add_cat:locs:{tid}"),
            types.InlineKeyboardButton("🔗 Ссылка", callback_data=f"add_cat:links:{tid}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="add_cancel")
        )
        bot.send_message(cid, "➕ **ДОБАВЛЕНИЕ ДАННЫХ**\nЧто вы хотите добавить в этот проект?", 
                         reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка добавления: {e}")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Проект А` (Бот должен быть админом)", parse_mode="Markdown")
            return

        # Attempt to rename topic
        bot.edit_forum_topic(cid, tid, name=new_name)
        
        # Also update in DB
        supabase.table("clients").update({"name": new_name}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        bot.reply_to(message, f"✅ Топик переименован в **{new_name}** и обновлен в базе.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}\n(Проверьте, является ли бот администратором с правом управления темами)")

@bot.message_handler(commands=['del'])
def handle_delete(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        # 1. CONTEXTUAL MODE (Reply)
        if message.reply_to_message:
            reply = message.reply_to_message
            txt = (reply.text or reply.caption or "")
            
            # 1.1 Check for Links
            urls = re.findall(r'(https?://[^\s]+)', txt)
            if urls:
                deleted_urls = []
                for url in urls:
                    res = supabase.table("project_resources").delete().eq("chat_id", cid).eq("thread_id", tid).eq("url", url).execute()
                    if res.data: deleted_urls.append(url)
                
                if deleted_urls:
                    bot.reply_to(message, f"🗑️ Удалено ресурсов: {len(deleted_urls)}")
                    return

            # 1.2 Check for Bot Confirmations (Contacts)
            c_match = re.search(r"Контакт \*\*(.*?)\*\* \((.*?)\) сохранен", txt)
            if c_match:
                ph = c_match.group(2)
                supabase.table("contacts").delete().eq("phone", ph).eq("thread_id", tid).execute()
                bot.reply_to(message, f"🗑️ Контакт **{c_match.group(1)}** удален из проекта.")
                return

            # 1.3 Check for Bot Confirmations (Locations)
            l_match = re.search(r"Локация \*\*(.*?)\*\*", txt)
            if l_match and "сохранена" in txt:
                loc_name = l_match.group(1)
                p_res = supabase.from_("clients").select("id").eq("chat_id", cid).eq("thread_id", tid).execute()
                if p_res.data:
                    pid = p_res.data[0]['id']
                    supabase.table("project_locations").delete().eq("project_id", pid).eq("name", loc_name).execute()
                    bot.reply_to(message, f"🗑️ Локация **{loc_name}** удалена из проекта.")
                    return

            # If reply but no data found, just fall through to the Menu!
            # The user might be replying to bot's own instruction or something irrelevant.

        # 2. INTERACTIVE MODE (Menu)
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👥 Актеры", callback_data=f"del_cat:actors:{tid}"),
            types.InlineKeyboardButton("📍 Локации", callback_data=f"del_cat:locs:{tid}"),
            types.InlineKeyboardButton("🔗 Ссылки", callback_data=f"del_cat:links:{tid}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")
        )
        bot.send_message(cid, "🧹 **ОЧИСТКА ДАННЫХ**\nВы можете удалить данные этого проекта:", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка удаления: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def handle_add_callback(call):
    try:
        cid = call.message.chat.id
        tid = call.message.message_thread_id
        data = call.data.split(':')
        cmd = data[0]

        if cmd == "add_cancel":
            bot.delete_message(cid, call.message.message_id)
            return

        if cmd == "add_cat":
            cat = data[1]
            prompts = {
                "actors": "👤 Отправьте имя актера или карточку контакта:",
                "crew": "🛠 Отправьте имя сотрудника или карточку контакта:",
                "clients": "🤝 Отправьте имя клиента или карточку контакта:",
                "locs": "📍 Отправьте название локации:",
                "links": "🔗 Отправьте ссылку (URL):"
            }
            # Use ForceReply to catch the answer
            bot.send_message(cid, prompts.get(cat, "Отправьте данные:"), 
                                   reply_markup=types.ForceReply(selective=True), 
                                   message_thread_id=tid)
            bot.answer_callback_query(call.id)
            
        elif cmd == "add_back":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("👥 Актер", callback_data=f"add_cat:actors:{tid}"),
                types.InlineKeyboardButton("🛠 Сотрудник", callback_data=f"add_cat:crew:{tid}"),
                types.InlineKeyboardButton("🤝 Клиент", callback_data=f"add_cat:clients:{tid}"),
                types.InlineKeyboardButton("📍 Локация", callback_data=f"add_cat:locs:{tid}"),
                types.InlineKeyboardButton("🔗 Ссылка", callback_data=f"add_cat:links:{tid}"),
                types.InlineKeyboardButton("❌ Отмена", callback_data="add_cancel")
            )
            bot.edit_message_text("➕ **ДОБАВЛЕНИЕ ДАННЫХ**\nЧто вы хотите добавить в этот проект?", 
                                 cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id)
def handle_reply_input(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        orig_text = message.reply_to_message.text
        
        # Identify category from prompt emoji
        cat = None
        if "👤" in orig_text: cat = "actors"
        elif "🛠" in orig_text: cat = "crew"
        elif "🤝" in orig_text: cat = "clients"
        elif "📍" in orig_text: cat = "locs"
        elif "🔗" in orig_text: cat = "links"
        
        if not cat: return 

        if cat in ["actors", "crew", "clients"]:
            name = ""
            phone = "—"
            if message.contact:
                name = f"{message.contact.first_name} {message.contact.last_name or ''}".strip()
                phone = message.contact.phone_number
            else:
                name = (message.text or "").strip()
            
            if not name: return

            db_cat = "casting" if cat == "actors" else ("media" if cat == "clients" else "crew")
            
            supabase.table("contacts").upsert({
                "name": name, "phone": phone, "thread_id": tid, "chat_id": cid, "category": db_cat
            }, on_conflict="phone,chat_id,thread_id").execute()
            
            bot.reply_to(message, f"✅ **{name}** сохранен в разделе категорий.")

        elif cat == "locs":
            loc_name = (message.text or "").strip()
            if not loc_name: return
            p_res = supabase.from_("clients").select("id").eq("chat_id", cid).eq("thread_id", tid).execute()
            if p_res.data:
                pid = p_res.data[0]['id']
                supabase.table("project_locations").upsert({"project_id": pid, "name": loc_name}, on_conflict="project_id, name").execute()
                bot.reply_to(message, f"✅ Локация **{loc_name}** добавлена в проект.")

        elif cat == "links":
            url = (message.text or "").strip()
            if not url: return
            if not url.startswith('http'): url = 'https://' + url
            supabase.table("project_resources").upsert({"chat_id": cid, "thread_id": tid, "url": url}, on_conflict="chat_id,thread_id,url").execute()
            bot.reply_to(message, f"✅ Ссылка сохранена в ресурсах проекта.")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка сохранения: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def handle_del_callback(call):
    try:
        cid = call.message.chat.id
        tid = call.message.message_thread_id
        data = call.data.split(':')
        cmd = data[0]

        if cmd == "del_cancel":
            bot.delete_message(cid, call.message.message_id)
            return

        if cmd == "del_cat":
            cat = data[1]
            markup = types.InlineKeyboardMarkup()
            
            if cat == "actors":
                res = supabase.table("contacts").select("id, name, phone").eq("chat_id", cid).eq("thread_id", tid).execute()
                for item in (res.data or []):
                    markup.add(types.InlineKeyboardButton(f"🗑 {item['name']} ({item['phone']})", callback_data=f"del_exe:contacts:{item['id']}"))
            elif cat == "locs":
                p_res = supabase.from_("clients").select("id").eq("chat_id", cid).eq("thread_id", tid).execute()
                if p_res.data:
                    pid = p_res.data[0]['id']
                    res = supabase.table("project_locations").select("id, name").eq("project_id", pid).execute()
                    for item in (res.data or []):
                        markup.add(types.InlineKeyboardButton(f"🗑 {item['name']}", callback_data=f"del_exe:project_locations:{item['id']}"))
            elif cat == "links":
                res = supabase.table("project_resources").select("id, url").eq("chat_id", cid).eq("thread_id", tid).execute()
                for item in (res.data or []):
                    # Shorten URL for display
                    short_url = item['url'].replace('https://', '').replace('http://', '')[:25] + '...'
                    markup.add(types.InlineKeyboardButton(f"🗑 {short_url}", callback_data=f"del_exe:project_resources:{item['id']}"))

            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"del_back:{tid}"))
            
            bot.edit_message_text("Выберите элемент для удаления:", cid, call.message.message_id, reply_markup=markup)

        elif cmd == "del_back":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("👥 Актеры", callback_data=f"del_cat:actors:{tid}"),
                types.InlineKeyboardButton("📍 Локации", callback_data=f"del_cat:locs:{tid}"),
                types.InlineKeyboardButton("🔗 Ссылки", callback_data=f"del_cat:links:{tid}"),
                types.InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")
            )
            bot.edit_message_text("🧹 **ОЧИСТКА ДАННЫХ**\nЧто именно вы хотите удалить?", cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif cmd == "del_exe":
            table, item_id = data[1], data[2]
            res = supabase.table(table).delete().eq("id", item_id).execute()
            if not res.data:
                raise Exception("Ничего не удалено. Возможно, запись уже удалена или нет прав.")
            bot.answer_callback_query(call.id, "✅ Удалено")
            # Return to categories
            handle_del_callback(types.CallbackQuery(id=call.id, from_user=call.from_user, chat_instance=call.chat_instance, message=call.message, data=f"del_back:{tid}"))

    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")

@app.route('/api/casting', methods=['POST', 'OPTIONS'])
def notify_casting():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        data = request.json or {}
        cid = data.get('chat_id')
        tid = data.get('thread_id')
        
        if not cid: return jsonify({'error': 'No chat_id'}), 400

        # Cast to integers
        cid = int(cid)
        tid = int(tid) if tid else None

        print(f"DEBUG: notify_casting for project: {data.get('project_name')} in chat: {cid}, thread: {tid}")

        # 1. Auto-Register Contact
        try:
            name, phone = data.get('full_name'), data.get('phone')
            if name and phone:
                supabase.table("contacts").upsert({
                    "name": name, "phone": phone, "thread_id": tid, "chat_id": cid, "category": "casting"
                }, on_conflict="phone,chat_id,thread_id").execute()
        except: pass

        # 2. Format Message (HTML for better reliability)
        def v(k): return str(data.get(k) or "—").replace("<", "&lt;").replace(">", "&gt;")
        
        # IMPROVED LAYOUT
        full_txt = (
            f"🌟 <b>НОВАЯ АНКЕТА: {v('full_name')}</b>\n"
            f"🎯 Кастинг: <b>{v('casting_target')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Личные данные:</b>\n"
            f"📍 {v('city')} | {v('gender')}\n"
            f"🎂 Возраст: <b>{v('dob')}</b>\n"
            f"🎭 Внешность: {v('nationality')}\n\n"
            f"📏 <b>Параметры:</b>\n"
            f"📈 Рост/Вес: <b>{v('height_weight')}</b>\n"
            f"👟 Размеры: <b>{v('sizes')}</b>\n\n"
            f"📱 <b>Контакты:</b>\n"
            f"🔗 Inst: {v('instagram')}\n"
            f"📞 WhatsApp: {v('phone')}\n\n"
            f"💡 <b>Опыт:</b>\n{v('experience')}\n\n"
            f"🎭 <b>Навыки:</b>\n{v('skills')}\n\n"
            f"💎 <b>Финансы и Прочее:</b>\n"
            f"💰 Бюджет: {v('fee_range')}\n"
            f"👙 Белье: {v('underwear_ok')} | Массовка: {v('extras_ok')}\n"
        )
        if data.get('portfolio_url'):
            full_txt += f"\n🔗 <a href='{data.get('portfolio_url')}'>Портфолио / Ссылка</a>\n"

        photos = data.get('photo_urls', [])
        video = data.get('video_audition_url')

        # DOUBLE-SAFETY: Add direct links to the message text
        if photos or video:
            full_txt += f"\n🖼️ <b>МЕДИА-ФАЙЛЫ (ПРЯМЫЕ ССЫЛКИ):</b>\n"
            for i, p_url in enumerate(photos):
                full_txt += f"• <a href='{p_url}'>Фото {i+1}</a>\n"
            if video:
                full_txt += f"• <a href='{video}'>Видео-визитка</a>\n"

        # USE A SIMPLE SAFE CAPTION FOR MEDIA GROUP to avoid 1024 limit and HTML breakage
        simple_caption = (
            f"📸 <b>Анкета: {v('full_name')}</b>\n"
            f"🎯 {v('casting_target')}\n\n"
            f"Описание придет следующим сообщением... ⬇️"
        )

        photos = data.get('photo_urls', [])
        video = data.get('video_audition_url')

        media = []
        for i, url in enumerate(photos):
            if i == 0:
                media.append(types.InputMediaPhoto(url, caption=simple_caption, parse_mode="HTML"))
            else:
                media.append(types.InputMediaPhoto(url))
        
        if video:
            if not media:
                media.append(types.InputMediaVideo(video, caption=simple_caption, parse_mode="HTML"))
            else:
                media.append(types.InputMediaVideo(video))

        try:
            sent_msg = None
            if media:
                print(f"DEBUG: sending media group with {len(media)} items")
                bot.send_media_group(cid, media, message_thread_id=tid)
                # 3. Always send full text as a separate message for guaranteed delivery
                sent_msg = bot.send_message(cid, full_txt, message_thread_id=tid, parse_mode="HTML", disable_web_page_preview=True)
            else:
                print(f"DEBUG: sending text message only")
                sent_msg = bot.send_message(cid, full_txt, message_thread_id=tid, parse_mode="HTML")
            
            # 4. CAPTURE MESSAGE ID to DB for future edits
            if sent_msg:
                try:
                    # Find the record that was just inserted by the frontend
                    # Searching by phone and chat/thread within the last hour
                    supabase.table("casting_applications")\
                        .update({"tg_message_id": sent_msg.message_id})\
                        .eq("phone", data.get('phone'))\
                        .eq("chat_id", cid)\
                        .execute()
                except Exception as db_e: print(f"DB Update Error: {db_e}")

            print("✅ SUCCESS: Notification sent to Telegram")
        except Exception as bot_err:
            print(f"❌ BOT SEND ERROR: {bot_err}")
            # Fallback to pure text message
            try:
                bot.send_message(cid, f"⚠️ Ошибка медиа. Данные анкеты:\n\n{full_txt}", message_thread_id=tid, parse_mode="HTML")
            except Exception as e2:
                print(f"❌ FALLBACK FAILED: {e2}")

        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        return res
    except Exception as e:
        print(f"Casting Notify Error: {e}")
        r = jsonify({'error': str(e)}); r.headers.add('Access-Control-Allow-Origin', '*'); return r, 500

# --- ADD VIDEO / MEDIA COMMAND ---
@bot.message_handler(func=lambda m: (m.text and "/add_video" in m.text) or (m.caption and "/add_video" in m.caption), content_types=['text', 'photo', 'video', 'document'])
def handle_add_video(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой, чтобы добавить медиа.")
            return

        # 1. SMART TARGET DETECTION (Chain Discovery)
        # We need to find the BOT's notification message (the "Application")
        target_reply = reply
        source_msg = message # By default, media is in the command message itself
        
        # If the reply is NOT the bot's application (no "АНКЕТА:")...
        if "АНКЕТА:" not in (reply.text or reply.caption or ""):
            # Maybe we are replying to a video/photo?
            if reply.video or reply.photo or reply.document:
                source_msg = reply # The media is what we replied to
                # Does THIS media reply to the application?
                if reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or ""):
                    target_reply = reply.reply_to_message
                else:
                    # Let's try to search naming anyway, but we need a target_reply
                    pass

        # Now search DB by target_reply.message_id
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", target_reply.message_id).execute()
        app_data = None
        
        if not res.data:
            # SMART HEALING: Search by name in text
            txt = target_reply.text or target_reply.caption or ""
            m_name = re.search(r'АНКЕТА:\s*([^\n<]+)', txt, re.IGNORECASE)
            found_name = m_name.group(1).strip().replace("<b>", "").replace("</b>", "") if m_name else None
            
            if found_name:
                h_res = supabase.table("casting_applications").select("*").ilike("full_name", f"%{found_name}%").eq("chat_id", message.chat.id).execute()
                if h_res.data:
                    app_data = h_res.data[0]
                    supabase.table("casting_applications").update({"tg_message_id": target_reply.message_id}).eq("id", app_data['id']).execute()
                else:
                    bot.reply_to(message, f"❌ Не удалось найти в базе анкету на имя '{found_name}'.")
                    return
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ.")
                return
        else:
            app_data = res.data[0]
        
        # 2. Extract Media from source_msg
        new_url = None
        file_id = None
        media_type = "файл"
        
        if source_msg.video: 
            file_id = source_msg.video.file_id
            media_type = "видео"
        elif source_msg.photo: 
            file_id = source_msg.photo[-1].file_id
            media_type = "фото"
        elif source_msg.document: 
            file_id = source_msg.document.file_id
            media_type = "файл"
        
        if file_id:
            # UPLOAD FILE TO SUPABASE
            bot.send_chat_action(message.chat.id, 'upload_document', message_thread_id=message.message_thread_id)
            f_info = bot.get_file(file_id)
            f_bytes = bot.download_file(f_info.file_path)
            
            ext = f_info.file_path.split('.')[-1]
            fname = f"additional_{app_data['id']}_{int(datetime.now().timestamp())}.{ext}"
            path = f"extra/{fname}" # Store extra stuff in a separate folder
            
            supabase.storage.from_('casting_media').upload(path, f_bytes)
            # Get public link
            new_url = supabase.storage.from_('casting_media').get_public_url(path)
            if not new_url:
                new_url = f"{SUPABASE_URL}/storage/v1/object/public/casting_media/{path}"
        else:
            # Search for link in text (Manual Link)
            txt = (message.text or message.caption or "").replace("/add_video", "").strip()
            m = re.search(r'(https?://[^\s]+)', txt)
            if m: 
                new_url = m.group(1)
                media_type = "ссылка"

        if not new_url:
            bot.reply_to(message, "❌ Файл или ссылка не найдены. Прикрепите фото/видео или напишите ссылку в ответе.")
            return

        # 3. Update DB
        current_extra = app_data.get('additional_media') or []
        if not isinstance(current_extra, list): current_extra = []
        current_extra.append({'type': media_type, 'url': new_url, 'added_at': datetime.now().isoformat()})
        
        supabase.table("casting_applications").update({"additional_media": current_extra}).eq("id", app_data['id']).execute()

        # 4. EDIT ORIGINAL BOT MESSAGE (The main Magic)
        new_text = reply.html_text
        if "МЕДИА-ФАЙЛЫ (ПРЯМЫЕ ССЫЛКИ):" not in new_text:
            new_text += "\n\n🖼️ <b>МЕДИА-ФАЙЛЫ (ПРЯМЫЕ ССЫЛКИ):</b>\n"
        
        # Determine the label based on media type
        label = f"Доп. {media_type.capitalize()}"
        if len(current_extra) > 1:
            label += f" {len(current_extra)}"
            
        new_text += f"• <a href='{new_url}'>{label}</a> (через Telegram)\n"
        
        try:
            bot.edit_message_text(new_text, message.chat.id, reply.message_id, parse_mode="HTML", disable_web_page_preview=True)
            # Notify user quietly
            bot.send_message(message.chat.id, f"✅ {media_type.capitalize()} добавлено в анкету <b>{app_data['full_name']}</b>", 
                             message_thread_id=message.message_thread_id, parse_mode="HTML")
        except Exception as edit_err:
            print(f"Edit Error: {edit_err}")
            # If edit failed (e.g. message too old), still let the user know
            bot.send_message(message.chat.id, f"✅ Данные сохранены в базу, но не удалось отредактировать сообщение (возможно, оно слишком старое).", 
                             message_thread_id=message.message_thread_id)

        # 5. Cleanup: Delete the user's command message
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except: pass
        
    except Exception as e:
        print(f"Add Media Error: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка при добавлении: {e}", message_thread_id=message.message_thread_id)

# --- END ADD VIDEO ---

@app.route('/api/timer/report_ping', methods=['POST', 'OPTIONS', 'GET'])
def report_ping():
    """Debug endpoint: test if shift data is readable and Excel can be built, without sending Telegram message."""
    r = app.make_response('')
    r.headers.add('Access-Control-Allow-Origin', '*')
    r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    r.headers.add('Access-Control-Allow-Methods', 'POST, GET')
    if request.method == 'OPTIONS': return r
    
    try:
        data = request.json or request.args or {}
        shift_id = data.get('shift_id')
        if not shift_id: return jsonify({'error': 'No shift_id'}), 400
        
        s_res = supabase.table('production_shifts').select("id, project_id, chat_id, thread_id, start_time, end_time, status").eq('id', shift_id).execute()
        if not s_res.data: return jsonify({'error': 'Shift not found'}), 404
        shift = s_res.data[0]
        
        l_res = supabase.table('production_logs').select("id, event_type, event_time").eq('shift_id', shift_id).execute()
        logs = l_res.data or []
        
        resp = jsonify({
            'status': 'ok',
            'shift': shift,
            'log_count': len(logs),
            'event_types': list(set(l['event_type'] for l in logs))
        })
        resp.headers.add('Access-Control-Allow-Origin', '*')
        return resp
    except Exception as e:
        import traceback
        r2 = jsonify({'error': str(e), 'trace': traceback.format_exc()})
        r2.headers.add('Access-Control-Allow-Origin', '*')
        return r2, 500


@app.route('/api/timer/report', methods=['POST', 'OPTIONS'])
def generate_timer_report():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
        
    try:
        data = request.json or {}
        shift_id = data.get('shift_id')
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        
        if not shift_id: return jsonify({'error': 'No shift_id'}), 400

        # 1. Fetch Data
        s_res = supabase.table('production_shifts').select("*").eq('id', shift_id).execute()
        if not s_res.data: return jsonify({'error': 'Shift not found'}), 404
        shift = s_res.data[0]
        
        l_res = supabase.table('production_logs').select("*").eq('shift_id', shift_id).order('event_time').execute()
        logs = l_res.data
        print(f"Logs found: {len(logs) if logs else 0}")
        if not logs:
            return jsonify({'error': 'No logs found for this shift', 'shift_id': shift_id}), 404

        df_logs = pd.DataFrame(logs)

        # --- CRITICAL: Parse 'data' field — Supabase may return JSON strings ---
        def parse_data(x):
            if isinstance(x, dict): return x
            if isinstance(x, str):
                try: return json.loads(x)
                except: return {}
            return {}
        df_logs['data'] = df_logs['data'].apply(parse_data)

        # Handle both timezone-aware and naive timestamps robustly
        raw_times = pd.to_datetime(df_logs['event_time'])
        if raw_times.dt.tz is None:
            df_logs['time'] = raw_times.dt.tz_localize('UTC').dt.tz_convert('Asia/Almaty')
        else:
            df_logs['time'] = raw_times.dt.tz_convert('Asia/Almaty')

        # Pre-compute start/end times (needed for Summary and filename below)
        raw_start = pd.to_datetime(shift['start_time'])
        if raw_start.tzinfo is None:
            raw_start = raw_start.tz_localize('UTC')
        start_t = raw_start.tz_convert('Asia/Almaty')

        if shift.get('end_time'):
            raw_end = pd.to_datetime(shift['end_time'])
            if raw_end.tzinfo is None:
                raw_end = raw_end.tz_localize('UTC')
            end_t = raw_end.tz_convert('Asia/Almaty')
        else:
            end_t = df_logs['time'].max()

        # 2. Create Excel with Formatting
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 0: ПРОТОКОЛ СЪЕМКИ (The New Main Sheet)
            protocol = []
            try:
                plan = json.loads(shift.get('schedule', '[]'))
                if not isinstance(plan, list): plan = []
                
                # Pre-process logs for easier lookup
                # motor, relocation_start, lunch_start, etc.
                for i, p_row in enumerate(plan):
                    num = p_row.get('num', '')
                    task_name = p_row.get('task', p_row.get('notes', '—'))
                    planned_time = f"{p_row.get('start','--:--')}—{p_row.get('end','--:--')}"
                    planned_loc = p_row.get('loc', '—')
                    
                    # Find actual data
                    # Check if any log refers to this plan row
                    actual_start = "—"
                    actual_end = "—"
                    duration = "—"
                    result = "—"
                    
                    # Find first log with this plan_row
                    row_logs = df_logs[df_logs['data'].apply(lambda x: (x.get('plan_row') or {}).get('num') == num if num else False)]
                    if row_logs.empty and not num:
                        # Fallback for tech tasks by name
                        tech_name = task_name.lower()
                        row_logs = df_logs[df_logs['event_type'].str.contains(tech_name, na=False)]

                    if not row_logs.empty:
                        start_evt = row_logs.iloc[0]
                        actual_start = start_evt['time'].strftime('%H:%M')
                        
                        # Find end (if motor) or just next event
                        end_candidates = df_logs[df_logs['time'] > start_evt['time']]
                        if not end_candidates.empty:
                            actual_end = end_candidates.iloc[0]['time'].strftime('%H:%M')
                            duration = round((end_candidates.iloc[0]['time'] - start_evt['time']).total_seconds() / 60)
                        
                        # If scene, count takes
                        if num:
                            takes = df_logs[(df_logs['event_type'] == 'motor') & 
                                            (df_logs['data'].apply(lambda x: x.get('scene_no') == str(num)))]
                            good_takes = df_logs[(df_logs['event_type'] == 'take_evaluation') & 
                                                 (df_logs['data'].apply(lambda x: x.get('result') == 'good'))]
                            result = f"{len(takes)} дуб. / {len(good_takes)} GOOD"

                    protocol.append({
                        '№': f"№{num}" if num else i+1,
                        'СЦЕНА / ЗАДАЧА': task_name,
                        'ЛОКАЦИЯ': planned_loc,
                        'ПЛАН (Н-К)': planned_time,
                        'ФАКТ (СТАРТ)': actual_start,
                        'ФАКТ (ФИН)': actual_end,
                        'ХРОН (МИН)': duration,
                        'РЕЗУЛЬТАТ / ДУБЛИ': result,
                        'ПЕРСОНАЖИ / ПРИМ.': f"{p_row.get('act', '')} | {p_row.get('notes', '')}".strip(" |")
                    })
            except Exception as ex: 
                print(f"Protocol error: {ex}")
                protocol = [{'Ошибка': str(ex)}]

            pd.DataFrame(protocol).to_excel(writer, sheet_name='ПРОТОКОЛ СЪЕМКИ', index=False)

            # Sheet 1: Chronology
            chrono = []
            for _, row in df_logs.iterrows():
                d = row['data'] or {}
                chrono.append({
                    'Время': row['time'].strftime('%H:%M:%S'),
                    'Событие': row['event_type'].upper().replace('_', ' '),
                    'Локация': d.get('loc', '-'),
                    'Сцена': d.get('scene_no', '-'),
                    'Кадр': d.get('shot_no', '-'),
                    'Дубль': d.get('take_no', '-'),
                    'Детали': json.dumps(d, ensure_ascii=False) if d else ''
                })
            pd.DataFrame(chrono).to_excel(writer, sheet_name='Хронология', index=False)

            # Sheet 2: Delays
            delays = []
            for _, row in df_logs[df_logs['event_type'].str.contains('delay', case=False)].iterrows():
                d = row['data'] or {}
                delays.append({
                    'Время': row['time'].strftime('%H:%M:%S'),
                    'Категория': row['event_type'].replace('delay_', '').upper(),
                    'Сцена': d.get('scene_no', '-'),
                    'Причина': d.get('reason', d.get('resolution', '-'))
                })
            pd.DataFrame(delays).to_excel(writer, sheet_name='Задержки', index=False)

            # Sheet 3: Prep
            prep_data = []
            prep_types = {'makeup':'ГРИМ','wardrobe':'КОСТЮМ','sound':'ОПЕТЛИЧИВАНИЕ','light':'СВЕТ','camera':'КАМЕРА','art':'ХУДОЖКА','props':'РЕКВИЗИТ','sfx':'ПИРОТЕХНИКА','stunts':'КАСКАДЕРЫ'}
            for pt_id, pt_label in prep_types.items():
                starts = df_logs[df_logs['event_type'] == f'{pt_id}_start']
                ends = df_logs[df_logs['event_type'] == f'{pt_id}_end']
                for _, s_row in starts.iterrows():
                    promised = (s_row['data'] or {}).get('promised', '?')
                    e_match = ends[ends['time'] > s_row['time']].head(1)
                    if not e_match.empty:
                        e_row = e_match.iloc[0]
                        actual_min = round((e_row['time'] - s_row['time']).total_seconds() / 60)
                        prep_data.append({
                            'Сервис': pt_label, 'Старт': s_row['time'].strftime('%H:%M'), 'Финиш': e_row['time'].strftime('%H:%M'),
                            'План (мин)': promised, 'Факт (мин)': actual_min, 'Задержка': max(0, actual_min - int(promised)) if str(promised).isdigit() else 0
                        })
            pd.DataFrame(prep_data).to_excel(writer, sheet_name='Подготовка', index=False)

            # Sheet 4: Arrivals
            arrivals = []
            arrival_types = ['crew_arrival', 'actor_arrival', 'client_arrival', 'actor_departure']
            arrival_logs = df_logs[df_logs['event_type'].isin(arrival_types)]
            for _, row in arrival_logs.iterrows():
                d = row['data'] or {}
                arrivals.append({
                    'Время': row['time'].strftime('%H:%M:%S'), 'Событие': row['event_type'].upper().replace('_', ' '),
                    'Имя': d.get('name', 'N/A'), 'Объект': d.get('loc', '-')
                })
            pd.DataFrame(arrivals).to_excel(writer, sheet_name='Прибытие', index=False)

            # Sheet 5: Summary
            all_data = df_logs['data'].apply(lambda x: x if isinstance(x, dict) else {})
            summary = [
                {'Параметр': 'Дата', 'Значение': start_t.strftime('%d.%m.%Y')},
                {'Параметр': 'Начало смены', 'Значение': start_t.strftime('%H:%M:%S')},
                {'Параметр': 'Конец смены', 'Значение': end_t.strftime('%H:%M:%S') if shift.get('end_time') else 'В работе'},
                {'Параметр': 'Общее время', 'Значение': str(end_t - start_t).split('.')[0]},
                {'Параметр': 'Всего сцен', 'Значение': all_data.apply(lambda x: x.get('scene_no', 0)).max()},
                {'Параметр': 'Всего кадров', 'Значение': all_data.apply(lambda x: x.get('shot_no', 0)).max()},
                {'Параметр': 'Всего дублей', 'Значение': len(df_logs[df_logs['event_type'].isin(['motor', 'take_increment', 'series'])])},
            ]
            pd.DataFrame(summary).to_excel(writer, sheet_name='Итоги', index=False)

            # APPLY FORMATTING
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            center_align = Alignment(horizontal='center')
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                # Auto-width and Styles
                for col in ws.columns:
                    max_length = 0
                    column = col[0].column_letter # Get the column name
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except: pass
                        cell.border = thin_border
                    ws.column_dimensions[column].width = max_length + 4
                
                # Header Style
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = center_align

        output.seek(0)
        file_bytes = output.read()
        file_name = f"DPR_{start_t.strftime('%d%m')}_Shift_{shift_id}.xlsx"
        
        # 4. Send to Telegram
        print(f"Request chat_id={chat_id}, thread_id={thread_id}")
        print(f"DB shift chat_id={shift.get('chat_id')}, thread_id={shift.get('thread_id')}")
        try:
            # ALWAYS prefer the DB value — frontend params may be empty strings
            db_chat = shift.get('chat_id')   # saved at shift start, most reliable
            db_thread = shift.get('thread_id')
            
            # Use request param only as override when DB value missing
            req_chat = None
            req_thread = None
            try:
                if chat_id and str(chat_id).strip():
                    req_chat = int(str(chat_id).strip())
            except (ValueError, TypeError): pass
            try:
                if thread_id and str(thread_id).strip():
                    req_thread = int(str(thread_id).strip())
            except (ValueError, TypeError): pass
            
            target_chat = db_chat or req_chat
            target_thread = db_thread or req_thread
            
            print(f"Using target_chat={target_chat}, target_thread={target_thread}")
            
            if not target_chat:
                raise ValueError(f"Missing chat_id for report delivery. DB={db_chat}, req={req_chat}")

            total_takes = len(df_logs[df_logs['event_type'].isin(['motor', 'take_increment', 'series'])])
            project_name = shift.get('project_id') or shift.get('project') or 'N/A'
            
            print(f"Sending document '{file_name}' to chat {target_chat}, thread {target_thread}, takes={total_takes}")
            msg = bot.send_document(
                target_chat, 
                (file_name, file_bytes), 
                caption=f"📋 **ОТЧЕТ ЗА СМЕНУ (DPR)**\n📅 Дата: {start_t.strftime('%d.%m.%Y')}\n🎬 Проект: {project_name}\n⏱ Смена: {start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}\n🔥 Всего дублей: {total_takes}", 
                message_thread_id=target_thread, 
                visible_file_name=file_name, 
                parse_mode="Markdown"
            )
            print(f"Document sent successfully, msg_id={msg.message_id if msg else None}")
            
            # --- AUTOMATED LINKING ---
            if msg and shift.get('shoot_id'):
                s_cid = str(target_chat)
                if s_cid.startswith("-100"): s_cid = s_cid[4:]
                report_link = f"https://t.me/c/{s_cid}/{msg.message_id}"
                
                print(f"Auto-linking report to shoot {shift['shoot_id']}: {report_link}")
                supabase.table('shoots').update({'report_link': report_link}).eq('id', shift['shoot_id']).execute()
            # -------------------------

        except Exception as tel_err:
            print(f"Telegram send error: {tel_err}")
            # Try sending to a fallback or just log it
            raise tel_err

        report_link = None
        if msg:
            s_cid = str(target_chat)
            if s_cid.startswith("-100"): s_cid = s_cid[4:]
            report_link = f"https://t.me/c/{s_cid}/{msg.message_id}"

        res = jsonify({'status': 'ok', 'report_link': report_link})
        res.headers.add('Access-Control-Allow-Origin', '*')
        return res
    except Exception as e:
        print(f"Report generator error: {e}")
        import traceback
        traceback.print_exc()
        r = jsonify({'error': str(e)}); r.headers.add('Access-Control-Allow-Origin', '*'); return r, 500

def ensure_project(chat_id, thread_id, chat_title, content="", message=None, forced_name=None):
    """Ensures a project (topic) exists. Returns (category, is_new)."""
    try:
        if not thread_id: return 'media', False
        category = 'casting' if 'КАСТИНГ' in (chat_title or "").upper() else 'media'
        
        # 1. Exact Match by Thread
        p_res = supabase.from_("clients").select("*").eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
        
        # 1b. Try match by Thread only if Chat ID is Null (Legacy Migration)
        if not p_res.data:
            p_res = supabase.from_("clients").select("*").is_("chat_id", "null").eq("thread_id", thread_id).execute()
            if p_res.data:
                # Fill in missing chat_id
                supabase.from_("clients").update({"chat_id": chat_id}).eq("id", p_res.data[0]['id']).execute()

        if p_res.data:
            p = p_res.data[0]
            # Update category just in case (e.g. if topic moved to another group)
            if p.get('category') != category:
                supabase.from_("clients").update({"category": category}).eq("id", p['id']).execute()

            # Auto-activate if ✅ added to thread name (heuristic: chat_title contains it)
            if '✅' in (chat_title or "") and not p.get('is_active'):
                supabase.from_("clients").update({"is_active": True}).eq("id", p['id']).execute()
                return category, False
            return category, p['name'].startswith("Project ")

        # 2. Forced Name or Heuristic Discovery
        if forced_name:
            is_active = '✅' in forced_name
            supabase.from_("clients").insert({
                "thread_id": thread_id, "chat_id": chat_id, "name": forced_name, 
                "category": category, "is_active": is_active
            }).execute()
            return category, False

        # Discovery (The "Brief" pattern)
        insta, name_v = "", ""
        u_m = re.search(r'instagram\.com/([^/?#\s]+)', content)
        at_m = re.search(r'@([\w._]+)', content)
        if u_m: insta = u_m.group(1)
        elif at_m: insta = at_m.group(1)

        words = [w for w in content.split() if w and w[0].isupper() and not w.startswith(('http', '@', '#')) and len(w) > 1]
        if words: name_v = words[0]

        if insta or name_v:
            prefix = "Casting: " if category == 'casting' else ""
            t_name = f"{prefix}{insta} | {name_v}" if insta and name_v else (prefix + (insta or name_v))
            is_active = '✅' in t_name
            supabase.from_("clients").insert({
                "thread_id": thread_id, "chat_id": chat_id, "name": t_name, 
                "category": category, "is_active": is_active
            }).execute()
            if message: bot.reply_to(message, f"✅ Проект определен: **{t_name}**" + (" (Активен)" if is_active else ""))
            return category, False

        # 3. Interactive Naming Flow (via Reply)
        if message and message.reply_to_message and "Как назовем этот проект?" in (message.reply_to_message.text or ""):
            new_name = content.strip()
            
            # Handle "нет" to hide topic
            if new_name.lower() == "нет":
                supabase.from_("clients").update({"is_hidden": True}).eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
                bot.reply_to(message, "🤐 Понял, этот топик будет скрыт из списков на сайте.")
                return category, False

            is_active = '✅' in new_name
            ex = supabase.from_("clients").select("*").ilike("name", f"%{new_name}%").execute()
            if ex.data and not ex.data[0].get('thread_id'):
                supabase.from_("clients").update({
                    "thread_id": thread_id, "chat_id": chat_id, "category": category, "is_active": is_active
                }).eq("id", ex.data[0]['id']).execute()
                bot.reply_to(message, f"🔗 Проект **{ex.data[0]['name']}** привязан к этому топику.")
                return category, False
            else:
                supabase.from_("clients").insert({
                    "thread_id": thread_id, "chat_id": chat_id, "name": new_name, 
                    "category": category, "is_active": is_active
                }).execute()
                bot.reply_to(message, f"✅ Проект создан: **{new_name}**" + (" (Активен)" if is_active else ""))
                return category, False

        # 4. Fallback - Ask for Name
        if message:
            bot.send_message(chat_id, f"🆕 Вижу новый топик в **{category}**!\nКак назовем этот проект? (ответь на это сообщение)", message_thread_id=thread_id)
        
        supabase.from_("clients").insert({
            "thread_id": thread_id, "chat_id": chat_id, "name": f"Project {thread_id}", "category": category
        }).execute()
        return category, True
    except Exception as e:
        print(f"ensure_project err: {e}"); return 'media', False

@bot.message_handler(commands=['actor', 'client'])
def handle_manual_contact(message):
    try:
        cmd = message.text.split()[0].lower().strip('/')
        args = message.text.replace(f'/{cmd}', '').strip()
        if not args:
            bot.reply_to(message, f"📝 Формат: `/{cmd} [телефон] [Имя]`\nПример: `/{cmd} 87012223344 Иван`", parse_mode="Markdown")
            return

        cid, tid = message.chat.id, (message.message_thread_id if message.is_topic_message else None)
        ensure_project(cid, tid, message.chat.title, args)

        clean_args = re.sub(r'[\s\-()\[\]]', '', args)
        ph_match = re.search(r'((\+?7|8)\d{10})', clean_args)
        if not ph_match:
            bot.reply_to(message, "❌ Не нашел номера телефона в сообщении.")
            return

        raw_ph = ph_match.group(1)
        ph = raw_ph
        if ph.startswith('8'): ph = '+7' + ph[1:]
        elif ph.startswith('7') and not ph.startswith('+'): ph = '+' + ph
        elif not ph.startswith('+'): ph = '+7' + ph

        name = args.replace(raw_ph, '').strip()
        category = 'casting' if cmd == 'actor' else 'media'

        try:
            supabase.table("contacts").upsert({
                "name": name, "phone": ph, "thread_id": tid, "chat_id": cid, "category": category
            }, on_conflict="phone,chat_id,thread_id").execute()
            bot.reply_to(message, f"✅ **{cmd.capitalize()}** сохранен: **{name}** ({ph})")
        except Exception as ex: bot.reply_to(message, f"❌ Ошибка базы данных: {ex}")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['staff'])
def handle_manual_staff(message):
    try:
        args = message.text.replace('/staff', '').strip().split(maxsplit=2)
        if len(args) < 2:
            bot.reply_to(message, f"📝 Формат: `/staff [ID или @username] [Имя] [Должность]`", parse_mode="Markdown")
            return

        identity, name = args[0].lstrip('@'), args[1]
        pos = args[2] if len(args) > 2 else "Сотрудник"

        r = ["task"]
        if any(x in pos.lower() for x in ["оператор", "камера"]): r += ["production", "post"]
        if any(x in pos.lower() for x in ["админ", "менеджер"]): r = ["production", "post", "task", "actor"]

        rec = {"full_name": name, "position": pos, "roles": list(set(r))}
        if identity.isdigit():
            rec["telegram_id"] = int(identity)
            supabase.from_("team").upsert(rec, on_conflict="telegram_id").execute()
        else:
            rec["username"] = identity
            supabase.from_("team").upsert(rec, on_conflict="username").execute()
        bot.reply_to(message, f"✅ Сотрудник **{name}** добавлен.")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка: {e}")

def register_user(user, chat_id, thread_id=None, silent=False):
    try:
        if not user: return None
        uid = getattr(user, 'id', None)
        username = (getattr(user, 'username', "") or "").lstrip('@').lower()
        if uid:
            res = supabase.from_("team").select("*").eq("telegram_id", uid).execute()
            if res.data: return res.data[0]

        if username:
            res = supabase.from_("team").select("*").ilike("username", username).execute()
            if res.data:
                supabase.from_("team").update({"telegram_id": uid}).eq("id", res.data[0]['id']).execute()
                return res.data[0]

        all_t = supabase.from_("team").select("*").execute()
        first, last = (getattr(user, 'first_name', "") or ""), (getattr(user, 'last_name', "") or "")
        f_low = f"{first} {last}".strip().lower()
        match = next((t for t in (all_t.data or []) if (t.get('full_name') or "").lower() == f_low), None)

        if match:
            supabase.from_("team").update({"telegram_id": uid}).eq("id", match['id']).execute()
            return match

        rec = {"telegram_id": uid, "username": username, "full_name": f"{first} {last}".strip(), "roles": ["task"]}
        supabase.from_("team").insert(rec).execute()
        if not silent:
            bot.send_message(chat_id, f"👋 Привет, {first}! Какая у тебя **Должность**? (ответь на это сообщение)", message_thread_id=thread_id)
        return None
    except Exception as e: print(f"Reg err: {e}"); return None

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    tid = message.message_thread_id if message.is_topic_message else None
    for u in (message.new_chat_members or []):
        if not u.is_bot: register_user(u, message.chat.id, tid)

@bot.message_handler(content_types=['forum_topic_closed'])
def handle_topic_closed(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        print(f"DEBUG: Catch forum_topic_closed in chat {cid}, thread {tid}")
        if tid:
            supabase.from_("clients").update({"is_hidden": True, "is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
            print(f"✅ SUCCESS: Topic {tid} in chat {cid} CLOSED and HIDDEN.")
    except Exception as e: print(f"❌ Topic Closed Err: {e}")

@bot.message_handler(content_types=['forum_topic_reopened'])
def handle_topic_reopened(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        print(f"DEBUG: Catch forum_topic_reopened in chat {cid}, thread {tid}")
        if tid:
            supabase.from_("clients").update({"is_hidden": False, "is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
            print(f"✅ SUCCESS: Topic {tid} in chat {cid} REOPENED and REVEALED.")
    except Exception as e: print(f"❌ Topic Reopened Err: {e}")

# Catch-all logger for debugging service messages
@bot.message_handler(func=lambda m: True, content_types=['forum_topic_created', 'forum_topic_edited', 'forum_topic_closed', 'forum_topic_reopened', 'general_forum_topic_hidden', 'general_forum_topic_unhidden'])
def debug_topic_events(message):
    print(f"🔍 DEBUG: Topic Event Type: {message.content_type} in Chat {message.chat.id}, Thread {message.message_thread_id}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    try:
        user = message.from_user
        if not user or user.is_bot: return
        content = (message.text or message.caption or "").strip()
        cid, tid = message.chat.id, (message.message_thread_id if message.is_topic_message else None)
        category = 'casting' if 'КАСТИНГ' in (message.chat.title or "").upper() else 'media'

        clean_c = re.sub(r'[\s\-()\[\]]', '', content)
        ph_match = re.search(r'((\+?7|8)\d{10})', clean_c)
        is_ph, is_cmd = (ph_match is not None), content.startswith('/')

        # 1. Reply Handling (Highest Priority)
        if message.reply_to_message and content:
            if message.reply_to_message.from_user.username == bot.get_me().username:
                b_txt = (message.reply_to_message.text or message.reply_to_message.caption or "")
                
                # 1.1 Project Naming via Reply
                if "Как назовем этот проект?" in b_txt:
                    ensure_project(cid, tid, message.chat.title, content, message=message)
                    return

                # 1.2 Saving Contact via Reply
                pm = re.search(r"`(\+7\d{10})`", b_txt)
                if pm and tid:
                    ph, name = pm.group(1), content
                    # If user replies "Да" or "Yes" and it was a global suggestion
                    if content.lower() in ["да", "yes", "ок", "ok", "давай", "верно"] and "уже записан как" in b_txt:
                        m_name = re.search(r"\*\*(.*?)\*\*", b_txt)
                        if m_name: name = m_name.group(1)
                    
                    try:
                        supabase.table("contacts").upsert({
                            "name": name, "phone": ph, "thread_id": tid, "chat_id": cid, "category": category
                        }, on_conflict="phone,chat_id,thread_id").execute()
                        bot.reply_to(message, f"✅ Контакт **{name}** ({ph}) сохранен!")
                        return
                    except Exception as ex:
                        bot.reply_to(message, f"❌ Ошибка: {ex}"); return

                # 1.3 Saving Position via Reply
                if "**Должность**" in b_txt:
                    pos = content
                    try:
                        r = ["task"]
                        if any(x in pos.lower() for x in ["оператор", "камера"]): r += ["production", "post"]
                        if any(x in pos.lower() for x in ["админ", "менеджер"]): r = ["production", "post", "task", "actor"]
                        supabase.from_("team").update({"position": pos, "roles": list(set(r))}).eq("telegram_id", user.id).execute()
                        bot.reply_to(message, f"✅ Должность **{pos}** сохранена!"); return
                    except Exception as ex:
                        bot.reply_to(message, f"❌ Ошибка: {ex}"); return

        # 1.4 Link Detection
        urls = re.findall(r'(https?://[^\s]+)', content)
        if urls and tid:
            for url in urls:
                try:
                    supabase.table("project_resources").upsert({
                        "chat_id": cid, "thread_id": tid, "url": url, 
                        "username": user.username or user.first_name
                    }, on_conflict="chat_id,thread_id,url").execute()
                except Exception as ex: print(f"Link capture err: {ex}")

        # 2. Discovery (Topics Only)
        if tid and content and not is_cmd:
            cat, is_new = ensure_project(cid, tid, message.chat.title, content, message=message)
            
            # 2.2 Phone Discovery (Only if project is NOT brand new and awaiting naming)
            if is_ph and not is_new:
                ph = ph_match.group(1)
                if ph.startswith('8'): ph = '+7' + ph[1:]
                elif ph.startswith('7') and not ph.startswith('+'): ph = '+' + ph
                elif not ph.startswith('+'): ph = '+7' + ph
                
                if len(ph) != 12: ph = '+7' + ph[-10:]

                try:
                    # Check in this topic
                    c_ex = supabase.table("contacts").select("*").eq("phone", ph).eq("chat_id", cid).eq("thread_id", tid).execute()
                    if c_ex.data:
                        bot.reply_to(message, f"📱 Номер `{ph}` уже записан как **{c_ex.data[0]['name']}** в этом проекте.")
                        return

                    # Check globally
                    c_glob = supabase.table("contacts").select("*").eq("phone", ph).limit(1).execute()
                    if c_glob.data:
                        g_name = c_glob.data[0]['name']
                        bot.reply_to(message, f"📱 Номер `{ph}` уже записан в базе как **{g_name}**.\nДобавить его в этот проект? (Ответьте **Да** или напишите новое имя)")
                        return
                    else:
                        bot.reply_to(message, f"📱 Вижу новый номер телефона: `{ph}`\nКак зовут этого человека? (Ответьте на это сообщение)")
                        return
                except Exception as ex: print(f"Ph disc err: {ex}"); return

        # 3. Identity & Registration (Last Priority)
        if not is_cmd and content:
            u_rec = register_user(user, message.chat.id, tid, silent=True)
            if u_rec and not u_rec.get('position'):
                bot.send_message(message.chat.id, f"📝 {user.first_name}, напиши свою **Должность** (ответь на это сообщение).", message_thread_id=tid)

    except Exception as e:
        print(f"Bot error: {e}")
        try: bot.reply_to(message, f"🚨 Ошибка бота: {e}")
        except: pass
