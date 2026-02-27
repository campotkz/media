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
SUPABASE_KEY = os.environ.get('SUPABASE_KEY') 
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
    cid = message.chat.id
    tid = message.message_thread_id or ''
    markup = types.InlineKeyboardMarkup()
    cal_url = f"{APP_URL}index.html?cid={cid}&tid={tid}"
    markup.add(types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", url=cal_url))
    bot.send_message(cid, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=tid or None, parse_mode="Markdown")

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

@bot.message_handler(commands=['cast_link', 'casting'])
def handle_universal_casting(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        # Universal link without project pre-selection
        link = f"{APP_URL}casting.html"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎭 ОТКРЫТЬ АНКЕТУ КАСТИНГА", url=link))
        
        msg = (
            f"🌟 <b>УНИВЕРСАЛЬНАЯ ССЫЛКА НА КАСТИНГ</b>\n\n"
            f"Эта ссылка позволяет кандидату выбрать любой активный проект внутри анкеты.\n\n"
            f"🔗 <code>{link}</code>\n\n"
            f"Все анкеты автоматически попадут в соответствующие топики проектов."
        )
        m = bot.send_message(cid, msg, reply_markup=markup, message_thread_id=tid, parse_mode="HTML")
        auto_delete(m, delay=60) # Universal link stays longer
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_sel:'))
def handle_app_select_callback(call):
    try:
        app_id = call.data.split(':')[1]
        cid = call.message.chat.id
        
        # 1. Get current status from DB
        res = supabase.table("casting_applications").select("is_selected, full_name").eq("id", app_id).execute()
        if not res.data:
            bot.answer_callback_query(call.id, "❌ Анкета не найдена.")
            return
        
        current_status = res.data[0].get('is_selected', False)
        new_status = not current_status
        actor_name = res.data[0].get('full_name', 'Актер')
        
        # 2. Update DB
        supabase.table("casting_applications").update({"is_selected": new_status}).eq("id", app_id).execute()
        
        # 3. Update Message (Add/Remove Checkmark in header)
        original_text = call.message.text or call.message.caption or ""
        new_text = original_text
        
        checkmark = "🟢 SELECTED: "
        if new_status:
            if checkmark not in original_text:
                new_text = checkmark + original_text
        else:
            new_text = original_text.replace(checkmark, "")
            
        # Update button text too
        markup = call.message.reply_markup
        for row in markup.keyboard:
            for btn in row:
                if btn.callback_data == call.data:
                    btn.text = "✅ ВЫБРАН" if new_status else "✅ ВЫБРАТЬ"
        
        try:
            bot.edit_message_text(new_text, cid, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except:
            # If it's a caption (media group)
            try: bot.edit_message_caption(new_text, cid, call.message.message_id, reply_markup=markup, parse_mode="HTML")
            except: pass
            
        status_msg = f"🌟 {actor_name} выбран!" if new_status else f"⚪️ Выбор снят: {actor_name}"
        bot.answer_callback_query(call.id, status_msg)

    except Exception as e:
        print(f"App Select Err: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при выборе.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_bl:'))
def handle_app_blacklist_initial(call):
    try:
        app_id = call.data.split(':')[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🏴 ДА, В ЧЕРНЫЙ СПИСОК", callback_data=f"app_bl_ok:{app_id}"),
            types.InlineKeyboardButton("❌ ОТМЕНА", callback_data=f"app_bl_no:{app_id}")
        )
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "⚠️ Добавить актера в ЧС навсегда?")
    except Exception as e:
        print(f"App BL Initial Err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_bl_no:'))
def handle_app_blacklist_cancel(call):
    try:
        app_id = call.data.split(':')[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ВЫБРАТЬ", callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}"),
            types.InlineKeyboardButton("🏴 ЧС", callback_data=f"app_bl:{app_id}")
        )
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "Отмена ЧС.")
    except Exception as e:
        print(f"App BL Cancel Err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_bl_ok:'))
def handle_app_blacklist_confirm(call):
    try:
        app_id = call.data.split(':')[1]
        cid = call.message.chat.id
        
        # 1. Fetch actor data
        res = supabase.table("casting_applications").select("*").eq("id", app_id).execute()
        if not res.data:
            bot.answer_callback_query(call.id, "❌ Ошибка: Анкета не найдена.")
            return
        
        app_data = res.data[0]
        phone = app_data.get('phone')
        insta = app_data.get('instagram')
        
        # 2. Add to Blacklist table
        supabase.table("blacklist").upsert({
            "phone": phone,
            "instagram": insta,
            "reason": "Added via Telegram Bot",
            "full_name": app_data.get('full_name')
        }, on_conflict="phone").execute()
        
        # 3. Permanent Delete from everywhere
        # (Reuse deletion logic manually)
        handle_app_delete_callback(types.CallbackQuery(id="0", from_user=call.from_user, chat_instance="0", 
                                                      message=call.message, data=f"app_del_ok:{app_id}"))
        
        bot.answer_callback_query(call.id, "🏴 АКТЕР В ЧЕРНОМ СПИСКЕ. Больше его анкеты не придут.")
    except Exception as e:
        print(f"App BL Confirm Err: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_del:'))
def handle_app_delete_initial(call):
    try:
        app_id = call.data.split(':')[1]
        cid = call.message.chat.id
        
        # Check current buttons to preserve Blacklist button if present
        current_markup = call.message.reply_markup
        has_blacklist = False
        if current_markup:
            for row in current_markup.keyboard:
                for btn in row:
                    if btn.callback_data and btn.callback_data.startswith('app_bl:'):
                        has_blacklist = True
                        break

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🗑️ ДА, УДАЛИТЬ", callback_data=f"app_del_ok:{app_id}"),
            types.InlineKeyboardButton("❌ ОТМЕНА", callback_data=f"app_del_no:{app_id}{':bl' if has_blacklist else ''}")
        )
        bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "⚠️ Вы уверены?")
    except Exception as e:
        print(f"App Del Initial Err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_del_no:'))
def handle_app_delete_cancel(call):
    try:
        parts = call.data.split(':')
        app_id = parts[1]
        has_blacklist = len(parts) > 2 and parts[2] == 'bl'

        markup = types.InlineKeyboardMarkup()
        
        btns = [
            types.InlineKeyboardButton("✅ ВЫБРАТЬ", callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
        ]
        if has_blacklist:
             btns.append(types.InlineKeyboardButton("🏴 ЧС", callback_data=f"app_bl:{app_id}"))
             
        markup.add(*btns)
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "Ок, отмена.")
    except Exception as e:
        print(f"App Del Cancel Err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_del_ok:'))
def handle_app_delete_callback(call):
    try:
        app_id = call.data.split(':')[1]
        cid = call.message.chat.id
        tid = call.message.message_thread_id
        
        # 1. Fetch data
        res = supabase.table("casting_applications").select("*").eq("id", app_id).execute()
        if not res.data:
            bot.answer_callback_query(call.id, "❌ Анкета уже удалена.")
            bot.delete_message(cid, call.message.message_id)
            return
        
        app_data = res.data[0]
        phone = app_data.get('phone')
        current_target = app_data.get('casting_target')
        
        # 2. Identify if we are in "Casting: ОБЩИЙ"
        is_general_topic = "ОБЩИЙ" in (current_target or "").upper()

        if is_general_topic:
            # 3. PERMANENT DELETE (Only from General)
            # 3.1 Cleanup Storage
            photos = app_data.get('photo_urls', [])
            video = app_data.get('video_audition_url')
            all_media_urls = list(photos)
            if video: all_media_urls.append(video)
            
            for url in all_media_urls:
                try:
                    if 'casting_media/' in url:
                        path = url.split('casting_media/')[-1]
                        supabase.storage.from_('casting_media').remove([path])
                except: pass
            
            # 3.2 Delete from DB and Contacts
            supabase.table("contacts").delete().eq("phone", phone).eq("thread_id", tid).eq("chat_id", cid).execute()
            supabase.table("casting_applications").delete().eq("id", app_id).execute()
            
            bot.answer_callback_query(call.id, "🗑️ Анкета удалена НАВСЕГДА.")
        else:
            # 4. TRANSFER TO GENERAL (Archive)
            # 4.1 Check if already in General
            gen_res = supabase.table("clients").select("chat_id, thread_id").ilike("name", "%ОБЩИЙ%").limit(1).execute()
            
            if gen_res.data:
                g_cid = gen_res.data[0]['chat_id']
                g_tid = gen_res.data[0]['thread_id']
                
                # Check if actor already has an application in General
                exists_in_gen = supabase.table("casting_applications").select("id")\
                    .eq("phone", phone).ilike("casting_target", "%ОБЩИЙ%").execute()
                
                if not exists_in_gen.data:
                    # Move to General: update DB record
                    supabase.table("casting_applications").update({
                        "casting_target": "Casting: ОБЩИЙ",
                        "project_name": "Casting: ОБЩИЙ",
                        "chat_id": g_cid,
                        "thread_id": g_tid,
                        "tg_message_id": None # Reset so it gets a new one in General
                    }).eq("id", app_id).execute()
                    
                    # Notify General Topic (Repost)
                    import requests
                    requests.post('https://media-seven-eta.vercel.app/api/casting', json={
                        **app_data,
                        "casting_target": "Casting: ОБЩИЙ",
                        "chat_id": g_cid,
                        "thread_id": g_tid
                    })
                    bot.answer_callback_query(call.id, "📦 Перенесено в ОБЩИЙ.")
                else:
                    # Already in General, just delete from current project
                    supabase.table("casting_applications").delete().eq("id", app_id).execute()
                    bot.answer_callback_query(call.id, "✅ Удалено (уже есть в ОБЩЕМ).")
            else:
                # No General topic found, just delete
                supabase.table("casting_applications").delete().eq("id", app_id).execute()
                bot.answer_callback_query(call.id, "✅ Удалено.")

            # Cleanup contacts for current project only
            if phone and tid:
                supabase.table("contacts").delete().eq("phone", phone).eq("thread_id", tid).eq("chat_id", cid).execute()

        # 5. Delete from Telegram (current chat)
        try:
            bot.delete_message(cid, call.message.message_id)
            try: bot.delete_message(cid, int(call.message.message_id) - 1)
            except: pass
        except: pass

    except Exception as e:
        print(f"App Delete Err: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка при удалении: {e}")

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
        phone = data.get('phone')
        insta = data.get('instagram')
        target = data.get('casting_target')
        
        if not cid: return jsonify({'error': 'No chat_id'}), 400

        # --- 0. BLACKLIST CHECK ---
        if phone or insta:
            bl_query = supabase.table("blacklist").select("id")
            if phone and insta:
                bl_query = bl_query.or_(f"phone.eq.{phone},instagram.eq.{insta}")
            elif phone:
                bl_query = bl_query.eq("phone", phone)
            elif insta:
                bl_query = bl_query.eq("instagram", insta)
            
            bl_res = bl_query.execute()
            if bl_res.data:
                print(f"🚫 BLOCKED: Application from {phone}/{insta} is in Blacklist.")
                return jsonify({'status': 'blocked', 'message': 'User is blacklisted'}), 200

        # Cast to integers
        cid = int(cid)
        tid = int(tid) if tid else None

        print(f"DEBUG: notify_casting for project: {target} (phone: {phone}, insta: {insta})")

        # 1. FIND AND DELETE OLD APPLICATION (Deduplication)
        try:
            # Search by phone OR instagram for the same project
            query = supabase.table("casting_applications").select("id, tg_message_id").eq("casting_target", target)
            
            # Complex OR filter for phone or instagram
            if phone and insta:
                query = query.or_(f"phone.eq.{phone},instagram.eq.{insta}")
            elif phone:
                query = query.eq("phone", phone)
            elif insta:
                query = query.eq("instagram", insta)
            
            # Get only records that ARE NOT the one just inserted (latest one has no tg_message_id yet)
            old_res = query.not_.is_("tg_message_id", "null").order("created_at", descending=True).execute()
            
            if old_res.data:
                for old_app in old_res.data:
                    old_msg_id = old_app.get('tg_message_id')
                    old_db_id = old_app.get('id')
                    
                    # 1.1 Delete from Telegram
                    if old_msg_id:
                        try:
                            # Also try to delete the media group message (it's usually msg_id - 1 if media was sent)
                            # Telegram doesn't give media group IDs easily, but we can try to delete previous 2 messages
                            # for safety if they belong to the same topic.
                            bot.delete_message(cid, old_msg_id)
                            # Optional: try to delete the media message too (sent just before text)
                            try: bot.delete_message(cid, int(old_msg_id) - 1)
                            except: pass
                        except Exception as tg_del_e: print(f"TG Delete Err: {tg_del_e}")
                    
                    # 1.2 Delete from Supabase
                    supabase.table("casting_applications").delete().eq("id", old_db_id).execute()
                    print(f"✅ Deduplicated: Deleted old application {old_db_id} for {phone}/{insta}")
        except Exception as dedup_e:
            print(f"Deduplication Error: {dedup_e}")

        # 2. Auto-Register Contact
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

        # 3. Inline Buttons (Select & Delete)
        markup = types.InlineKeyboardMarkup()
        try:
            app_res = supabase.table("casting_applications").select("id").eq("phone", phone).eq("casting_target", target).order("created_at", descending=True).limit(1).execute()
            if app_res.data:
                app_id = app_res.data[0]['id']
                
                btns = [
                    types.InlineKeyboardButton("✅ ВЫБРАТЬ", callback_data=f"app_sel:{app_id}"),
                    types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
                ]
                
                # Add Blacklist button ONLY for General topic
                if "ОБЩИЙ" in (target or "").upper():
                    btns.append(types.InlineKeyboardButton("🏴 ЧС", callback_data=f"app_bl:{app_id}"))
                
                markup.add(*btns)
        except: pass

        try:
            sent_msg = None
            if media:
                print(f"DEBUG: sending media group with {len(media)} items")
                try:
                    bot.send_media_group(cid, media, message_thread_id=tid)
                except Exception as mg_e:
                    print(f"❌ Media Group Send Failed: {mg_e}")
                    # If media group fails (e.g. invalid URL), fallback to sending just the text message
                    # or try sending photos one by one (simplified fallback)
                    full_txt += "\n⚠️ Не удалось загрузить медиа-файлы в виде альбома. Ссылки выше."
            
            # 3. Always send full text as a separate message for guaranteed delivery
            print(f"DEBUG: sending text message")
            try:
                sent_msg = bot.send_message(cid, full_txt, message_thread_id=tid, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
            except Exception as txt_e:
                print(f"❌ Text Send Failed (HTML): {txt_e}")
                # Fallback to plain text if HTML parsing fails
                sent_msg = bot.send_message(cid, full_txt.replace("<", "").replace(">", ""), message_thread_id=tid, reply_markup=markup)
            
            # 4. CAPTURE MESSAGE ID to DB for future edits
            if sent_msg:
                try:
                    # Find the latest record that was just inserted by the frontend
                    supabase.table("casting_applications")\
                        .update({"tg_message_id": sent_msg.message_id})\
                        .eq("phone", phone)\
                        .eq("casting_target", target)\
                        .is_("tg_message_id", "null")\
                        .execute()
                except Exception as db_e: print(f"DB Update Error: {db_e}")

            print("✅ SUCCESS: Notification sent to Telegram")
        except Exception as bot_err:
            print(f"❌ CRITICAL BOT SEND ERROR: {bot_err}")
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

@bot.message_handler(commands=['del'])
def handle_del_app_command(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой для удаления.")
            return

        # 1. FIND THE APPLICATION DATA
        target_reply = reply
        if "АНКЕТА:" not in (reply.text or reply.caption or ""):
            if reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or ""):
                target_reply = reply.reply_to_message
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ.")
                return

        res = supabase.table("casting_applications").select("id").eq("tg_message_id", target_reply.message_id).execute()
        if not res.data:
            bot.reply_to(message, "❌ Анкета не найдена в базе.")
            return
        
        app_id = res.data[0]['id']
        
        # Cleanup command
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        
        # Reuse callback logic
        handle_app_delete_callback(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", 
                                                      message=target_reply, data=f"app_del:{app_id}"))

    except Exception as e:
        print(f"Manual Del Error: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.forward_from_chat or m.forward_from)
def handle_forwarded_message(message):
    try:
        # Check if this is an application message being forwarded
        txt = message.text or message.caption or ""
        if "АНКЕТА:" not in txt:
            return

        cid, tid = message.chat.id, message.message_thread_id
        if not tid: return # Only handle topics

        # Extract name and phone/insta from text to find original record
        m_name = re.search(r'АНКЕТА:\s*([^\n<]+)', txt, re.IGNORECASE)
        m_phone = re.search(r'📞\s*([^\n<]+)', txt)
        m_insta = re.search(r'📱\s*Instagram:\s*([^\n<]+)', txt)

        found_name = m_name.group(1).strip().replace("<b>", "").replace("</b>", "") if m_name else None
        phone = m_phone.group(1).strip() if m_phone else None
        insta = m_insta.group(1).strip() if m_insta else None

        if not (phone or insta): return

        # 1. Ensure project (topic) exists in DB
        ensure_project(cid, tid, message.chat.title)
        p_res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
        new_project_name = p_res.data[0]['name'] if p_res.data else "Unknown"

        # 2. Update/Insert contact for THIS topic
        if phone:
            supabase.table("contacts").upsert({
                "name": found_name or "Unknown",
                "phone": phone,
                "chat_id": cid,
                "thread_id": tid,
                "category": "casting"
            }, on_conflict="phone,chat_id,thread_id").execute()

        # 3. Create a NEW entry in casting_applications for this project
        # Search for the most recent application by this actor to copy photos/video
        query = supabase.table("casting_applications").select("*")
        if phone: query = query.eq("phone", phone)
        elif insta: query = query.eq("instagram", insta)
        
        orig_res = query.order("created_at", descending=True).limit(1).execute()
        
        if orig_res.data:
            orig = orig_res.data[0]
            # Create NEW record for the NEW project
            new_app = {
                **orig,
                "casting_target": new_project_name,
                "project_name": new_project_name,
                "chat_id": cid,
                "thread_id": tid,
                "tg_message_id": message.message_id # Link to the forwarded message
            }
            # Remove keys that shouldn't be duplicated exactly or will be auto-generated
            new_app.pop('id', None)
            new_app.pop('created_at', None)
            
            supabase.table("casting_applications").insert([new_app]).execute()
            
            # 4. Add the Delete button to the forwarded message by sending a small "control" message
            markup = types.InlineKeyboardMarkup()
            # Find the ID of the newly created record
            fresh_res = supabase.table("casting_applications").select("id").eq("phone", phone).eq("casting_target", new_project_name).order("created_at", descending=True).limit(1).execute()
            if fresh_res.data:
                markup.add(types.InlineKeyboardButton("🗑️ УДАЛИТЬ ИЗ ЭТОГО ТОПИКА", callback_data=f"app_del:{fresh_res.data[0]['id']}"))
                conf_msg = bot.reply_to(message, f"✅ Актер **{found_name}** добавлен в проект **{new_project_name}**.", reply_markup=markup)
                
                # Auto-delete confirmation message after 10 seconds to keep chat clean
                import threading
                import time
                def delayed_delete(chat_id, msg_id):
                    time.sleep(10)
                    try: bot.delete_message(chat_id, msg_id)
                    except: pass
                
                threading.Thread(target=delayed_delete, args=(cid, conf_msg.message_id)).start()
            
            print(f"🔄 FORWARD SYNC: Actor {found_name} synced to new project {new_project_name}")

    except Exception as e:
        print(f"Forward Sync Err: {e}")

@bot.message_handler(commands=['foto', 'video'])
def handle_actor_update_link(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой актера.")
            return

        # Find the application in DB
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", reply.message_id).execute()
        if not res.data:
            # Try searching by name if message_id not found (old message)
            txt = reply.text or reply.caption or ""
            m_name = re.search(r'АНКЕТА:\s*([^\n<]+)', txt, re.IGNORECASE)
            if m_name:
                found_name = m_name.group(1).strip().replace("<b>", "").replace("</b>", "")
                res = supabase.table("casting_applications").select("*").ilike("full_name", f"%{found_name}%").eq("chat_id", message.chat.id).execute()
        
        if not res.data:
            bot.reply_to(message, "❌ Анкета не найдена в базе. Возможно, она слишком старая.")
            return

        app_data = res.data[0]
        update_type = 'photo' if 'foto' in message.text else 'video'
        
        # Generate Personal Link
        link = f"https://campotkz.github.io/media/update.html?id={app_data['id']}&type={update_type}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="📥 ЗАГРУЗИТЬ МАТЕРИАЛЫ", url=link))
        
        type_text = "фотографии" if update_type == 'photo' else "видео-визитку"
        msg = (
            f"👤 **АКТЕР:** {app_data['full_name']}\n"
            f"🔗 **ССЫЛКА ДЛЯ ОБНОВЛЕНИЯ:**\n\n"
            f"Скопируйте и отправьте актеру:\n"
            f"`{link}`\n\n"
            f"По этой ссылке он сможет загрузить дополнительные {type_text}. "
            f"После загрузки анкета в чате обновится автоматически."
        )
        
        m = bot.send_message(message.chat.id, msg, reply_markup=markup, message_thread_id=message.message_thread_id, parse_mode="Markdown")
        auto_delete(m, delay=60) # Link for actor stays longer
        
        # Cleanup command
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

    except Exception as e:
        print(f"Actor Update Link Err: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: (m.text and "/add" in m.text) or (m.caption and "/add" in m.caption), content_types=['text', 'photo', 'video', 'document'])
def handle_manual_add_media(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой, чтобы добавить медиа.")
            return

        # 1. FIND THE APPLICATION DATA
        target_reply = reply
        # If the reply is NOT the bot's application, try to find it in the chain
        if "АНКЕТА:" not in (reply.text or reply.caption or ""):
            if reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or ""):
                target_reply = reply.reply_to_message
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ.")
                return

        # 2. Check if media is already in the command message
        source_msg = message
        is_direct_upload = source_msg.video or source_msg.photo
        
        if not is_direct_upload:
            # Interactive mode: Ask user to send media
            prompt = bot.reply_to(message, "📥 **ОЖИДАНИЕ МЕДИА**\nПришлите фото или видео **ОТВЕТОМ** на это сообщение для анкеты актера.", parse_mode="Markdown")
            return

        # Direct mode logic (media already in /add message)
        process_manual_media_update(message, target_reply)

    except Exception as e:
        print(f"Manual Update Error: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", message_thread_id=message.message_thread_id)

def process_manual_media_update(source_msg, application_msg):
    try:
        cid, tid = source_msg.chat.id, source_msg.message_thread_id
        
        # Search DB by application_msg.message_id
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", application_msg.message_id).execute()
        if not res.data:
            bot.send_message(cid, "❌ Анкета не найдена в базе (возможно, она слишком старая).", message_thread_id=tid)
            return
        
        app_data = res.data[0]
        new_video = app_data.get('video_audition_url')
        new_photos = app_data.get('photo_urls') or []
        
        # 2. Extract Media (Video/Photo)
        is_updated = False
        if source_msg.video:
            bot.send_chat_action(cid, 'upload_video', message_thread_id=tid)
            f_info = bot.get_file(source_msg.video.file_id)
            f_bytes = bot.download_file(f_info.file_path)
            path = f"video/manual_{app_data['id']}_{int(datetime.now().timestamp())}.mp4"
            supabase.storage.from_('casting_media').upload(path, f_bytes)
            new_video = supabase.storage.from_('casting_media').get_public_url(path)
            is_updated = True
        elif source_msg.photo:
            bot.send_chat_action(cid, 'upload_photo', message_thread_id=tid)
            f_info = bot.get_file(source_msg.photo[-1].file_id)
            f_bytes = bot.download_file(f_info.file_path)
            path = f"photo/manual_{app_data['id']}_{int(datetime.now().timestamp())}.jpg"
            supabase.storage.from_('casting_media').upload(path, f_bytes)
            new_photos.append(supabase.storage.from_('casting_media').get_public_url(path))
            is_updated = True
            
        if not is_updated: return

        # 3. Update DB
        supabase.table("casting_applications").update({
            "photo_urls": new_photos,
            "video_audition_url": new_video
        }).eq("id", app_data['id']).execute()

        # 4. Trigger Repost
        updated_payload = {
            **app_data,
            "photo_urls": new_photos,
            "video_audition_url": new_video,
            "chat_id": cid,
            "thread_id": tid
        }

        # Delete OLD message
        try:
            bot.delete_message(cid, application_msg.message_id)
            try: bot.delete_message(cid, int(application_msg.message_id) - 1)
            except: pass
        except: pass

        # Delete command message and its parents if interactive
        try: bot.delete_message(cid, source_msg.message_id)
        except: pass
        if source_msg.reply_to_message and "ОЖИДАНИЕ МЕДИА" in (source_msg.reply_to_message.text or ""):
            try: 
                # Delete the "/add" command that triggered the prompt
                bot.delete_message(cid, source_msg.reply_to_message.reply_to_message.message_id)
                # Delete the bot prompt itself
                bot.delete_message(cid, source_msg.reply_to_message.message_id)
            except: pass

        # SEND NEW MESSAGE
        import requests
        requests.post('https://media-seven-eta.vercel.app/api/casting', json=updated_payload)

    except Exception as e:
        print(f"process_manual_media_update err: {e}")

# Handle replies to "ОЖИДАНИЕ МЕДИА" prompt
@bot.message_handler(func=lambda m: m.reply_to_message and "ОЖИДАНИЕ МЕДИА" in (m.reply_to_message.text or ""), content_types=['photo', 'video'])
def handle_media_reply_to_prompt(message):
    # Tracing: Media -> replies to Prompt -> Prompt replies to /add -> /add replies to Application
    # OR simpler: The Prompt itself replied to the application if we used reply_to_message correctly
    # Let's find the application message from the prompt's reply_to_message
    
    # Prompt was sent using bot.reply_to(message, ...), so prompt.reply_to_message is the /add command
    # /add command.reply_to_message is the Application
    
    prompt_msg = message.reply_to_message
    add_command_msg = prompt_msg.reply_to_message
    if not add_command_msg: return
    
    application_msg = add_command_msg.reply_to_message
    if not application_msg:
        # Fallback: maybe the prompt was a direct reply to application? 
        # (Though current logic uses reply to /add)
        if "АНКЕТА:" in (add_command_msg.text or add_command_msg.caption or ""):
            application_msg = add_command_msg
        else: return

    process_manual_media_update(message, application_msg)

# --- OLD ADD VIDEO ---
# I will replace it with the new unified handle_manual_add_media above.


@app.route('/api/timer/report_ping', methods=['POST', 'OPTIONS', 'GET'])
def report_ping():
    """Debug endpoint: test if shift data is readable and Excel can be built, without sending Telegram message."""
    r = app.make_response('')
    r.headers.add('Access-Control-Allow-Origin', '*')
    r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    r.headers.add('Access-Control-Allow-Methods', 'POST, GET')
    if request.method == 'OPTIONS': return r
    
    try:
        data = request.get_json(silent=True) or request.args or {}
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

        # 2. Create Excel with DPR Formatting
        output = io.BytesIO()
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side, GradientFill
        from openpyxl.utils import get_column_letter

        wb = Workbook()

        # ─── HELPER STYLES ────────────────────────────────────────────────────────
        def hdr_dark(ws, row, col, value, span=1, height=None):
            """Black-fill white-bold-centered header cell with optional merge."""
            cell = ws.cell(row=row, column=col, value=value)
            cell.fill = PatternFill("solid", fgColor="1A1A1A")
            cell.font = Font(color="FFFFFF", bold=True, size=9)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if span > 1:
                ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+span-1)
            if height:
                ws.row_dimensions[row].height = height
            return cell

        def hdr_red(ws, row, col, value, span=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.fill = PatternFill("solid", fgColor="CC0000")
            cell.font = Font(color="FFFFFF", bold=True, size=9)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if span > 1:
                ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+span-1)
            return cell

        def hdr_green(ws, row, col, value, span=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.fill = PatternFill("solid", fgColor="1E7E34")
            cell.font = Font(color="FFFFFF", bold=True, size=9)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if span > 1:
                ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+span-1)
            return cell

        def bordered(ws, row, col, value="", bold=False, bg=None, align="left", span=1, size=9):
            cell = ws.cell(row=row, column=col, value=value)
            cell.border = thin_border
            cell.font = Font(bold=bold, size=size)
            cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)
            if bg:
                cell.fill = PatternFill("solid", fgColor=bg)
            if span > 1:
                ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+span-1)
            return cell

        thin_s = Side(style="thin")
        thin_border = Border(left=thin_s, right=thin_s, top=thin_s, bottom=thin_s)
        med_s = Side(style="medium")
        med_border = Border(left=med_s, right=med_s, top=med_s, bottom=med_s)

        def auto_width(ws, min_w=8, max_w=40):
            for col in ws.columns:
                ml = min_w
                for cell in col:
                    try:
                        v = str(cell.value) if cell.value is not None else ""
                        ml = max(ml, min(len(v) + 2, max_w))
                    except: pass
                ws.column_dimensions[get_column_letter(col[0].column)].width = ml

        # ─── SHEET 1: PRODUCTION REPORT ──────────────────────────────────────────
        ws = wb.active
        ws.title = "PRODUCTION REPORT"
        ws.sheet_view.showGridLines = False

        # Parse plan from shift
        try:
            schedule = json.loads(shift.get('schedule') or '[]')
            if not isinstance(schedule, list): schedule = []
        except: schedule = []

        project_name = shift.get('project_id', 'N/A')
        shoot_id = shift.get('shoot_id')
        location_str = shift.get('location', '')
        # Try fetching location from shoot record
        if not location_str and shoot_id:
            try:
                shoot_r = supabase.table('shoots').select('location').eq('id', shoot_id).execute()
                if shoot_r.data: location_str = shoot_r.data[0].get('location', '')
            except: pass

        # All locations mentioned in logs
        loc_from_logs = df_logs['data'].apply(lambda x: x.get('loc', '') if isinstance(x, dict) else '').dropna().unique().tolist()
        loc_from_logs = [l for l in loc_from_logs if l]
        all_locs = location_str or ', '.join(loc_from_logs) or '—'

        day_names_ru = ['ПОНЕДЕЛЬНИК','ВТОРНИК','СРЕДА','ЧЕТВЕРГ','ПЯТНИЦА','СУББОТА','ВОСКРЕСЕНЬЕ']
        date_str = f"{start_t.strftime('%d.%m.%Y')}  {day_names_ru[start_t.weekday()]}"

        # --- Шапка (Header block) ---
        # Title row
        ws.merge_cells("A1:N1")
        title_cell = ws["A1"]
        title_cell.value = "PRODUCTION REPORT"
        title_cell.fill = PatternFill("solid", fgColor="1A1A1A")
        title_cell.font = Font(color="FFFFFF", bold=True, size=14)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 26

        # Row 2: Day | Company & Project
        ws.merge_cells("A2:E2"); ws.merge_cells("F2:J2"); ws.merge_cells("K2:N2")
        bordered(ws, 2, 1, f"СЪЕМОЧНЫЙ ДЕНЬ: {shift.get('day_number', 1)}", bold=True, bg="2C2C2C", align="center").font = Font(color="FFFFFF", bold=True, size=10)
        bordered(ws, 2, 6, f"ПРОЕКТ: {project_name}", bold=True, bg="2C2C2C").font = Font(color="FFFFFF", bold=True, size=10)
        bordered(ws, 2, 11, f"ДАТА: {date_str}", bold=True, bg="2C2C2C", align="center").font = Font(color="FFFFFF", bold=True, size=10)
        ws.row_dimensions[2].height = 20

        # Row 3: ON SET / WRAP | 1ST SHOT | LUNCH
        ws.merge_cells("A3:E3"); ws.merge_cells("F3:J3"); ws.merge_cells("K3:N3")
        first_motor = df_logs[df_logs['event_type'] == 'motor']['time'].min()
        lunch_start = df_logs[df_logs['event_type'] == 'lunch_start']['time'].min()
        lunch_end   = df_logs[df_logs['event_type'] == 'lunch_end']['time'].min()
        on_set_wrap = f"ON SET / WRAP:  {start_t.strftime('%H:%M')} / {end_t.strftime('%H:%M')}"
        first_shot_str = f"1ST SHOT:  {first_motor.strftime('%H:%M')}" if pd.notna(first_motor) else "1ST SHOT:  —"
        lunch_str = f"LUNCH:  {lunch_start.strftime('%H:%M') if pd.notna(lunch_start) else '—'} — {lunch_end.strftime('%H:%M') if pd.notna(lunch_end) else '—'}"
        bordered(ws, 3, 1, on_set_wrap, bg="F0F0F0", align="center")
        bordered(ws, 3, 6, first_shot_str, bg="F0F0F0", align="center")
        bordered(ws, 3, 11, lunch_str, bg="F0F0F0", align="center")
        ws.row_dimensions[3].height = 18

        # Row 4: LOCATION
        ws.merge_cells("A4:N4")
        loc_cell = ws.cell(row=4, column=1, value=f"LOCATION(S):  {all_locs.upper()}")
        loc_cell.fill = PatternFill("solid", fgColor="1A1A1A")
        loc_cell.font = Font(color="FFFFFF", bold=True, size=10)
        loc_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[4].height = 20

        # ─── COLUMN HEADERS for scene table (row 5) ──────────────────────────────
        COLS = [
            ('№',          1,  3), ('СЦЕНА /\nЗАДАЧА', 4, 18),
            ('ЛОКАЦИЯ',    22, 12), ('СИНОПСИС',        34, 16),
            ('АКТЕРЫ / ПЕРСОНАЖИ', 50, 16),
            ('ПЛАН\nН', 66, 7), ('ПЛАН\nК', 73, 7),
            ('ФАКТ\nН', 80, 7), ('ФАКТ\nК', 87, 7),
            ('ХРОН\nМИН',  94, 6),
            ('КАДРОВ', 100, 5), ('ДУБЛЕЙ', 105, 5), ('GOOD', 110, 5),
            ('ПРИМЕЧАНИЯ', 115, 12),
        ]
        # Compact mapping: each column in the worksheet maps to our logical column
        HEADERS = ['№', 'СЦЕНА /\nЗАДАЧА', 'ЛОКАЦИЯ', 'СИНОПСИС', 'АКТЕРЫ /\nПЕРСОНАЖИ',
                   'ПЛАН Н', 'ПЛАН К', 'ФАКТ Н', 'ФАКТ К', 'ХРОН\nМИН',
                   'КАДРОВ', 'ДУБЛЕЙ', 'GOOD', 'ПРИМЕЧАНИЯ']
        COL_WIDTHS = [4, 18, 14, 20, 18, 7, 7, 7, 7, 7, 6, 6, 6, 16]

        # Set column widths
        for ci, w in enumerate(COL_WIDTHS, 1):
            ws.column_dimensions[get_column_letter(ci)].width = w

        r = 5
        for ci, h in enumerate(HEADERS, 1):
            c = ws.cell(row=r, column=ci, value=h)
            c.fill = PatternFill("solid", fgColor="333333")
            c.font = Font(color="FFFFFF", bold=True, size=8)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = thin_border
        ws.row_dimensions[r].height = 28

        # ─── SCENE ROWS ──────────────────────────────────────────────────────────
        r = 6
        for p_row in schedule:
            num = str(p_row.get('num', ''))
            task = p_row.get('task', p_row.get('notes', ''))
            loc  = p_row.get('loc', '')
            syn  = p_row.get('synopsis', p_row.get('desc', ''))
            act  = p_row.get('act', p_row.get('actors', ''))
            p_start = p_row.get('start', '')
            p_end   = p_row.get('end', '')
            notes_txt = p_row.get('notes', '')

            # Actual times: find first log event tied to this scene number
            scene_logs = df_logs[df_logs['data'].apply(
                lambda x: str(x.get('scene_no', '')) == num if isinstance(x, dict) and num else False
            )] if num else pd.DataFrame()

            if not scene_logs.empty:
                a_start = scene_logs['time'].min().strftime('%H:%M')
                a_end   = scene_logs['time'].max().strftime('%H:%M')
                dur_min = round((scene_logs['time'].max() - scene_logs['time'].min()).total_seconds() / 60)
            else:
                a_start = ''; a_end = ''; dur_min = ''

            motors = df_logs[(df_logs['event_type'] == 'motor') &
                             (df_logs['data'].apply(lambda x: str(x.get('scene_no','')) == num if isinstance(x,dict) and num else False))]
            good_t = df_logs[(df_logs['event_type'] == 'take_evaluation') &
                             (df_logs['data'].apply(lambda x: str(x.get('scene_no','')) == num and x.get('result') == 'good' if isinstance(x,dict) and num else False))]
            shots_count = df_logs[(df_logs['event_type'].isin(['shot_increment','new_shot'])) &
                                  (df_logs['data'].apply(lambda x: str(x.get('scene_no','')) == num if isinstance(x,dict) and num else False))].shape[0]

            row_vals = [num, task, loc, syn, act,
                        p_start, p_end, a_start, a_end, dur_min if dur_min != '' else '',
                        shots_count or '', len(motors) or '', len(good_t) or '',
                        notes_txt]

            # Highlight if no actual data
            row_bg = None if a_start else "FFF9C4"  # light yellow if not shot

            for ci, val in enumerate(row_vals, 1):
                c = ws.cell(row=r, column=ci, value=val if val is not None else '')
                c.border = thin_border
                c.font = Font(size=8)
                c.alignment = Alignment(vertical="center", wrap_text=True,
                                        horizontal="center" if ci in [1,6,7,8,9,10,11,12,13] else "left")
                if row_bg:
                    c.fill = PatternFill("solid", fgColor=row_bg)
            ws.row_dimensions[r].height = 22
            r += 1

        # ─── NON-SCENE SCHEDULE ROWS (prep, moves, lunch etc.) ───────────────────
        # (already included in schedule above if present)

        # ─── BLANK ROW ───────────────────────────────────────────────────────────
        r += 1

        # ─── SUMMARY TOTALS ──────────────────────────────────────────────────────
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=14)
        c = ws.cell(row=r, column=1, value="ИТОГИ СЪЁМОЧНОГО ДНЯ")
        c.fill = PatternFill("solid", fgColor="1A1A1A"); c.font = Font(color="FFFFFF", bold=True, size=10)
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[r].height = 20; r += 1

        total_scenes = len([p for p in schedule if p.get('num')])
        total_shot = len(df_logs['data'].apply(lambda x: x.get('scene_no','') if isinstance(x,dict) else '').dropna().unique())
        total_takes = len(df_logs[df_logs['event_type'] == 'motor'])
        total_good  = len(df_logs[(df_logs['event_type'] == 'take_evaluation') &
                                   (df_logs['data'].apply(lambda x: isinstance(x,dict) and x.get('result')=='good'))])
        lunch_dur = ''
        if pd.notna(lunch_start) and pd.notna(lunch_end):
            lunch_dur = round((lunch_end - lunch_start).total_seconds() / 60)
        total_work_min = round((end_t - start_t).total_seconds() / 60) - (lunch_dur if lunch_dur else 0)

        summary_rows = [
            ('СЦЕН ПО ПЛАНУ', total_scenes, 'ВСЕГО ДУБЛЕЙ', total_takes),
            ('СЦЕН СНЯТО',    total_shot,   'GOOD TAKES',    total_good),
            ('НАЧАЛО СМЕНЫ',  start_t.strftime('%H:%M'), 'КОНЕЦ СМЕНЫ', end_t.strftime('%H:%M')),
            ('ОБЕД',          f"{lunch_start.strftime('%H:%M') if pd.notna(lunch_start) else '—'} — {lunch_end.strftime('%H:%M') if pd.notna(lunch_end) else '—'}" if lunch_dur else '—',
             'РАБОЧИХ МИН',   total_work_min),
        ]
        for lbl1, val1, lbl2, val2 in summary_rows:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)
            ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=11)
            ws.merge_cells(start_row=r, start_column=12, end_row=r, end_column=14)
            bordered(ws, r, 1, lbl1, bold=True, bg="2C2C2C", align="right").font = Font(color="FFFFFF", bold=True, size=9)
            bordered(ws, r, 5, val1, align="center")
            bordered(ws, r, 8, lbl2, bold=True, bg="2C2C2C", align="right").font = Font(color="FFFFFF", bold=True, size=9)
            bordered(ws, r, 12, val2, align="center")
            ws.row_dimensions[r].height = 18; r += 1

        # ─── ПЕРСОНАЖИ ───────────────────────────────────────────────────────────
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=14)
        hdr_red(ws, r, 1, "ПЕРСОНАЖИ / АКТЕРЫ")
        hdr_dark(ws, r, 8, "ГРУППОВКА / ЭПИЗОДНИКИ")
        ws.row_dimensions[r].height = 18; r += 1

        all_actors = set()
        for p in schedule:
            a = p.get('act', p.get('actors', ''))
            if a:
                for name in a.split(','):
                    if name.strip(): all_actors.add(name.strip())
        # Also from logs
        for _, row_l in df_logs[df_logs['event_type'] == 'actor_arrival'].iterrows():
            d = row_l['data'] if isinstance(row_l['data'], dict) else {}
            if d.get('name'): all_actors.add(d['name'])

        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=14)
        bordered(ws, r, 1, ', '.join(sorted(all_actors)) or '—')
        bordered(ws, r, 8, '—')
        ws.row_dimensions[r].height = 30; r += 2

        # ─── ЧАСЫ РАБОТЫ / ОТЧЕТ ВРЕМЕНИ ─────────────────────────────────────────
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=14)
        hdr_dark(ws, r, 1, "ЧАСЫ РАБОТЫ")
        hdr_dark(ws, r, 8, "ОТЧЕТ ВРЕМЕНИ")
        ws.row_dimensions[r].height = 18; r += 1

        time_rows = [
            ('ON SET / WRAP', f"{start_t.strftime('%H:%M')} / {end_t.strftime('%H:%M')}"),
            ('1ST SHOT', first_motor.strftime('%H:%M') if pd.notna(first_motor) else '—'),
            ('LUNCH', f"{lunch_start.strftime('%H:%M') if pd.notna(lunch_start) else '—'} — {lunch_end.strftime('%H:%M') if pd.notna(lunch_end) else '—'}"),
        ]
        report_rows = [
            ('СЕГОДНЯ', f"{total_work_min} мин"),
            ('НАРАСТАЮЩИЙ ИТОГ', '—'),
        ]
        for i, ((lbl, val), (rl, rv)) in enumerate(zip(time_rows, report_rows + [('','')])):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)
            ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=11)
            ws.merge_cells(start_row=r, start_column=12, end_row=r, end_column=14)
            bordered(ws, r, 1, lbl, bold=True, bg="F0F0F0", align="right")
            bordered(ws, r, 5, val, align="center")
            bordered(ws, r, 8, rl, bold=True, bg="F0F0F0", align="right")
            bordered(ws, r, 12, rv, align="center")
            ws.row_dimensions[r].height = 18; r += 1

        # ─── NOTES ────────────────────────────────────────────────────────────────
        r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=14)
        hdr_dark(ws, r, 1, "NOTES")
        ws.row_dimensions[r].height = 18; r += 1
        notes_logs = df_logs[df_logs['event_type'] == 'note']
        notes_txt_all = '; '.join([
            (row_l['data'] or {}).get('text', '') for _, row_l in notes_logs.iterrows()
            if isinstance(row_l['data'], dict) and row_l['data'].get('text')
        ]) or '—'
        ws.merge_cells(start_row=r, start_column=1, end_row=r+1, end_column=14)
        c = ws.cell(row=r, column=1, value=notes_txt_all)
        c.border = thin_border; c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 40

        # ─── SHEET 2: ХРОНОЛОГИЯ (Full event log) ────────────────────────────────
        ws2 = wb.create_sheet("ХРОНОЛОГИЯ")
        chrono_headers = ['ВРЕМЯ', 'СОБЫТИЕ', 'ЛОКАЦИЯ', 'СЦЕНА', 'КАДР', 'ДУБЛЬ', 'ДЕТАЛИ']
        for ci, h in enumerate(chrono_headers, 1):
            c = ws2.cell(row=1, column=ci, value=h)
            c.fill = PatternFill("solid", fgColor="1A1A1A"); c.font = Font(color="FFFFFF", bold=True, size=9)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = thin_border

        for ri, (_, row_l) in enumerate(df_logs.iterrows(), 2):
            d = row_l['data'] if isinstance(row_l['data'], dict) else {}
            vals = [
                row_l['time'].strftime('%H:%M:%S'),
                row_l['event_type'].upper().replace('_', ' '),
                d.get('loc', ''), d.get('scene_no', ''), d.get('shot_no', ''), d.get('take_no', ''),
                '; '.join(f"{k}={v}" for k, v in d.items() if k not in ['loc','scene_no','shot_no','take_no'])
            ]
            for ci, v in enumerate(vals, 1):
                c = ws2.cell(row=ri, column=ci, value=v)
                c.border = thin_border; c.font = Font(size=8)
                c.alignment = Alignment(vertical="center")

        for col in ws2.columns:
            ws2.column_dimensions[get_column_letter(col[0].column)].width = max(
                8, min(40, max((len(str(c.value or '')) for c in col), default=8) + 2))

        # ─── SHEET 3: ЗАДЕРЖКИ ────────────────────────────────────────────────────
        ws3 = wb.create_sheet("ЗАДЕРЖКИ")
        delay_headers = ['ВРЕМЯ', 'КАТЕГОРИЯ', 'СЦЕНА', 'ДЛИТЕЛЬНОСТЬ (МИН)', 'ПРИЧИНА']
        for ci, h in enumerate(delay_headers, 1):
            c = ws3.cell(row=1, column=ci, value=h)
            c.fill = PatternFill("solid", fgColor="CC0000"); c.font = Font(color="FFFFFF", bold=True, size=9)
            c.alignment = Alignment(horizontal="center"); c.border = thin_border

        delay_ri = 2
        delay_logs_typed = df_logs[df_logs['event_type'].str.contains('delay', case=False, na=False)]
        for _, row_l in delay_logs_typed.iterrows():
            d = row_l['data'] if isinstance(row_l['data'], dict) else {}
            # Find matching end
            end_row = df_logs[(df_logs['time'] > row_l['time']) &
                              (df_logs['event_type'].str.contains('delay_end|stop', na=False))].head(1)
            dur_d = ''
            if not end_row.empty:
                dur_d = round((end_row.iloc[0]['time'] - row_l['time']).total_seconds() / 60)
            for ci, v in enumerate([
                row_l['time'].strftime('%H:%M:%S'),
                row_l['event_type'].replace('_', ' ').upper(),
                d.get('scene_no', ''), dur_d,
                d.get('reason', d.get('resolution', ''))
            ], 1):
                c = ws3.cell(row=delay_ri, column=ci, value=v)
                c.border = thin_border; c.font = Font(size=8)
            delay_ri += 1

        for col in ws3.columns:
            ws3.column_dimensions[get_column_letter(col[0].column)].width = 18

        # Save workbook to BytesIO
        wb.save(output)
        output.seek(0)
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
            output.seek(0)  # make sure pointer is at start
            msg = bot.send_document(
                target_chat,
                output,
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
            if message: 
                m = bot.reply_to(message, f"✅ Проект определен: **{t_name}**" + (" (Активен)" if is_active else ""))
                auto_delete(m)
            return category, False

        # 3. Interactive Naming Flow (via Reply)
        if message and message.reply_to_message and "Как назовем этот проект?" in (message.reply_to_message.text or ""):
            new_name = content.strip()
            
            # Handle "нет" to hide topic
            if new_name.lower() == "нет":
                supabase.from_("clients").update({"is_hidden": True}).eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
                m = bot.reply_to(message, "🤐 Понял, этот топик будет скрыт из списков на сайте.")
                auto_delete(m)
                return category, False

            is_active = '✅' in new_name
            ex = supabase.from_("clients").select("*").ilike("name", f"%{new_name}%").execute()
            if ex.data and not ex.data[0].get('thread_id'):
                supabase.from_("clients").update({
                    "thread_id": thread_id, "chat_id": chat_id, "category": category, "is_active": is_active
                }).eq("id", ex.data[0]['id']).execute()
                m = bot.reply_to(message, f"🔗 Проект **{ex.data[0]['name']}** привязан к этому топику.")
                auto_delete(m)
                return category, False
            else:
                supabase.from_("clients").insert({
                    "thread_id": thread_id, "chat_id": chat_id, "name": new_name, 
                    "category": category, "is_active": is_active
                }).execute()
                m = bot.reply_to(message, f"✅ Проект создан: **{new_name}**" + (" (Активен)" if is_active else ""))
                auto_delete(m)
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
            m = bot.reply_to(message, f"✅ **{cmd.capitalize()}** сохранен: **{name}** ({ph})")
            auto_delete(m)
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
        m = bot.reply_to(message, f"✅ Сотрудник **{name}** добавлен.")
        auto_delete(m)
    except Exception as e: bot.reply_to(message, f"❌ Ошибка: {e}")

# --- HELPERS ---
def auto_delete(msg, delay=20):
    """Automatically deletes a message after N seconds."""
    if not msg: return
    def do_delete():
        import time
        time.sleep(delay)
        try: bot.delete_message(msg.chat.id, msg.message_id)
        except: pass
    import threading
    threading.Thread(target=do_delete).start()

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
            m = bot.send_message(chat_id, f"👋 Привет, {first}! Какая у тебя **Должность**? (ответь на это сообщение)", message_thread_id=thread_id)
            auto_delete(m, delay=60) # Give more time for greeting
        return None
    except Exception as e: print(f"Reg err: {e}"); return None

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    tid = message.message_thread_id if message.is_topic_message else None
    for u in (message.new_chat_members or []):
        if not u.is_bot: register_user(u, message.chat.id, tid)

@bot.message_handler(content_types=['forum_topic_created'])
def handle_topic_created(message):
    try:
        cid = message.chat.id
        # The title of the new topic is in forum_topic_created object
        topic_title = message.forum_topic_created.name
        tid = message.message_thread_id
        
        category = 'casting' if 'КАСТИНГ' in (message.chat.title or "").upper() else 'media'
        
        print(f"🆕 NEW TOPIC: {topic_title} (ID: {tid}) in Chat: {cid}")
        
        # Immediately save to DB with the correct name
        supabase.table("clients").upsert({
            "name": topic_title,
            "chat_id": cid,
            "thread_id": tid,
            "category": category,
            "is_active": True,
            "is_hidden": False
        }, on_conflict="chat_id,thread_id").execute()
        
        print(f"✅ SUCCESS: Project '{topic_title}' saved to DB automatically.")
    except Exception as e:
        print(f"❌ Topic Created Err: {e}")

@bot.message_handler(content_types=['forum_topic_edited'])
def handle_topic_edited(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        new_name = message.forum_topic_edited.name
        if tid and new_name:
            supabase.from_("clients").update({"name": new_name}).eq("chat_id", cid).eq("thread_id", tid).execute()
            print(f"📝 EDITED: Topic {tid} in chat {cid} renamed to '{new_name}'")
    except Exception as e: print(f"❌ Topic Edited Err: {e}")

@bot.message_handler(content_types=['forum_topic_deleted'])
def handle_topic_deleted(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if tid:
            # Delete project from clients
            supabase.from_("clients").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            # Also delete related contacts? (Optional but clean)
            # supabase.from_("contacts").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            print(f"🗑️ DELETED: Project from topic {tid} in chat {cid} removed from DB.")
    except Exception as e: print(f"❌ Topic Deleted Err: {e}")

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
