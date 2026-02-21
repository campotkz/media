import os
import telebot
import re
from telebot import types
from flask import Flask, request, jsonify
from supabase import create_client, Client

# Config
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" 
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Version indicator for debugging
VERSION = "1.5.1" 

@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
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
        data = request.json
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

@bot.message_handler(commands=['start', 'cal'])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", url=APP_URL))
    bot.send_message(message.chat.id, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=message.message_thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def handle_status(message):
    bot.reply_to(message, f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `{message.from_user.first_name}`\nID: `{message.from_user.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    cid, tid = message.chat.id, message.message_thread_id or ""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=f"{APP_URL}feedback.html?cid={cid}&tid={tid}"))
    bot.send_message(cid, f"📉 **СВЕРКА МЕТРИК**\n\n`{APP_URL}feedback.html?cid={cid}&tid={tid}`", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        tid = message.message_thread_id if message.is_topic_message else None
        if not tid:
            bot.reply_to(message, "❌ Эту команду нужно использовать внутри Топика (Проекта).")
            return
        
        new_name = message.text.replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Goldy | Luxury`", parse_mode="Markdown")
            return

        supabase.from_("clients").update({"name": new_name}).eq("thread_id", tid).execute()
        bot.reply_to(message, f"✅ Проект переименован: **{new_name}**")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}")

def register_user(user, chat_id, thread_id=None, silent=False):
    try:
        # Match by ID
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        if res.data: return res.data[0]

        # Match by Username or Name (Robustness)
        all_t = supabase.from_("team").select("*").execute()
        u_low = (user.username or "").lstrip('@').lower()
        # Safe way to get full name in telebot
        first = user.first_name or ""
        last = user.last_name or ""
        f_low = f"{first} {last}".strip().lower()
        
        match = None
        for t in (all_t.data or []):
            db_u = (t.get('username') or "").lstrip('@').lower()
            db_f = (t.get('full_name') or "").lower()
            # Try to match username OR full name
            if (u_low and db_u == u_low) or (f_low and db_f == f_low) or (first.lower() == db_f):
                match = t
                break
        
        if match:
            # Update the ID so we don't have to search next time
            supabase.from_("team").update({"telegram_id": user.id}).eq("id", match['id']).execute()
            return match
        
        # New
        rec = {"telegram_id": user.id, "username": user.username or "", "full_name": f"{first} {last}".strip(), "roles": ["task"]}
        supabase.from_("team").insert(rec).execute()
        if not silent:
            bot.send_message(chat_id, f"👋 Привет, {first}! Какая у тебя **Должность**?", message_thread_id=thread_id)
        return None
    except Exception as e:
        print(f"Reg err: {e}"); return None

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    tid = message.message_thread_id if message.is_topic_message else None
    for u in message.new_chat_members:
        if not u.is_bot: register_user(u, message.chat.id, tid)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    try:
        user = message.from_user
        if not user or user.is_bot: return
        
        # Safe content extraction (Text or Caption)
        content = (message.text or message.caption or "").strip()
        tid = message.message_thread_id if message.is_topic_message else None
        
        # Phone Detection (Immediate)
        clean_c = re.sub(r'[\s\-()\[\]]', '', content)
        ph_match = re.search(r'((\+?7|8)\d{10})', clean_c)
        is_ph = ph_match is not None
        is_cmd = content.startswith('/')

        # 1. Reply Handling (Highest Priority)
        if message.reply_to_message and content:
            # We check the text of the message being replied to
            b_txt = (message.reply_to_message.text or message.reply_to_message.caption or "")
            
            # 1.1 Saving Contact via Reply
            # Look for phone format: +7XXXXXXXXXX
            pm = re.search(r"`(\+7\d{10})`", b_txt)
            if pm and tid:
                ph, name = pm.group(1), content
                try:
                    supabase.table("contacts").upsert({"name": name, "phone": ph, "thread_id": tid}, on_conflict="phone,thread_id").execute()
                    bot.reply_to(message, f"✅ Контакт **{name}** ({ph}) сохранен!")
                    return
                except Exception as ex:
                    bot.reply_to(message, f"❌ Ошибка сохранения контакта: {ex}")
                    return

            # 1.2 Saving Position via Reply
            if "**Должность**" in b_txt:
                pos = content
                try:
                    r = ["task"]
                    if any(x in pos.lower() for x in ["оператор", "камера"]): r += ["production", "post"]
                    if any(x in pos.lower() for x in ["админ", "менеджер"]): r = ["production", "post", "task", "actor"]
                    supabase.from_("team").update({"position": pos, "roles": list(set(r))}).eq("telegram_id", user.id).execute()
                    bot.reply_to(message, f"✅ Должность **{pos}** сохранена!")
                    return
                except Exception as ex:
                    bot.reply_to(message, f"❌ Ошибка сохранения должности: {ex}")
                    return

        # 2. Discovery (Topics Only)
        if tid and content and not is_cmd:
            # 2.1 Project Sync (Only if not linked)
            p_res = supabase.from_("clients").select("*").eq("thread_id", tid).execute()
            if not p_res.data:
                insta, name_v = "", ""
                u_m = re.search(r'instagram\.com/([^/?#\s]+)', content)
                at_m = re.search(r'@([\w._]+)', content)
                if u_m: insta = u_m.group(1)
                elif at_m: insta = at_m.group(1)
                
                # Filter out formatting words and handles to find the project/person name
                words = [w for w in content.split() if w and w[0].isupper() and not w.startswith(('http', '@', '#')) and len(w) > 1]
                if words: name_v = words[0]
                
                t_name = f"{insta} | {name_v}" if insta and name_v else (insta or name_v or f"Project {tid}")
                ex = supabase.from_("clients").select("*").ilike("name", f"%{t_name}%").execute()
                if ex.data:
                    supabase.from_("clients").update({"thread_id": tid}).eq("id", ex.data[0]['id']).execute()
                    bot.reply_to(message, f"🔗 Проект **{ex.data[0]['name']}** привязан к топику.")
                    return
                else:
                    supabase.from_("clients").insert({"thread_id": tid, "name": t_name}).execute()
                    bot.reply_to(message, f"🆕 Проект зарегистрирован: **{t_name}**")
                    return

            # 2.2 Phone Discovery
            if is_ph:
                raw_ph = ph_match.group(1)
                ph = raw_ph
                if ph.startswith('8'): ph = '+7' + ph[1:]
                elif ph.startswith('7'): ph = '+' + ph
                elif not ph.startswith('+'): ph = '+7' + ph
                
                if len(ph) != 12: 
                    if len(raw_ph) == 10: ph = '+7' + raw_ph
                    else: ph = '+7' + raw_ph[-10:]

                c_ex = supabase.table("contacts").select("*").eq("phone", ph).eq("thread_id", tid).execute()
                if c_ex.data:
                    bot.reply_to(message, f"📱 Номер `{ph}` уже записан как **{c_ex.data[0]['name']}**. Хотите сменить имя? Ответьте на это сообщение новым именем.")
                    return
                else:
                    candidate_words = [w for w in content.split() if w and w[0].isupper() and len(w) > 1 and not w.startswith(('#', '@', 'http')) and not any(c in w for c in '+890')]
                    guess = " ".join(candidate_words[:2]) if candidate_words else None
                    
                    if guess:
                        try:
                            supabase.table("contacts").insert({"name": guess, "phone": ph, "thread_id": tid}).execute()
                            bot.reply_to(message, f"✅ Контакт: **{guess}** ({ph}) сохранен для этого проекта.")
                            return
                        except Exception as ex:
                            bot.reply_to(message, f"❌ Ошибка авто-сохранения контакта: {ex}")
                            return
                    else:
                        bot.reply_to(message, f"📱 Вижу номер телефона: `{ph}`\nКак зовут этого клиента (ответьте на ЭТО сообщение)?")
                        return

        # 3. Identity & Registration (Last Priority)
        if not is_cmd and content:
            u_rec = register_user(user, message.chat.id, tid, silent=True)
            # If user has no position, AND this message isn't a project/contact thing, try to use it as position
            if u_rec and not u_rec.get('position'):
                # Heuristic: If it's a short message (1-3 words) and no capitalized words (except maybe first), could be position
                # But to avoid mistakes, we'll only do this IF it was a response to the prompt.
                # Since we can't easily check 'context', we'll just keep the prompt but make it less frequent or better worded.
                bot.send_message(message.chat.id, f"📝 {user.first_name}, напиши свою **Должность** (ответь на это сообщение).", message_thread_id=tid)

    except Exception as e:
        print(f"Bot error: {e}")
        try:
            bot.reply_to(message, f"🚨 Критическая ошибка бота: {e}")
        except: pass
