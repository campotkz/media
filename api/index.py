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
        response = app.make_response('')
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    try:
        data = request.json
        chat_id, thread_id = data.get('chat_id'), data.get('thread_id')
        if not chat_id: return jsonify({'error': 'No chat_id'}), 400
        prev_query = supabase.table('client_feedback').select('leads_count, sales_count').eq('thread_id', thread_id or 0).order('created_at', desc=True).limit(2).execute()
        p_l, p_s = 0, 0
        if len(prev_query.data) > 1:
            p_l, p_s = prev_query.data[1]['leads_count'] or 0, prev_query.data[1]['sales_count'] or 0
        c_l, c_s = int(data.get('leads_count', 0)), int(data.get('sales_count', 0))
        d_l, d_s = c_l - p_l, c_s - p_s
        l_i, s_i = ("🟢" if d_l >= 0 else "🔴"), ("🟢" if d_s >= 0 else "🔴")
        def v(k): return str(data.get(k)) if data.get(k) else "-"
        msg = f"📊 **ОТЧЕТ ЗА МЕСЯЦ**\n\n👤 Имя: {v('client_name')}\nInst: {v('instagram')}\n\n🔥 Лиды: {c_l} ({d_l:+})\nПродажи: {c_s} ({d_s:+})"
        bot.send_message(chat_id, msg, message_thread_id=thread_id, parse_mode="Markdown")
        r = jsonify({'status': 'ok'})
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

@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    cid, tid = message.chat.id, message.message_thread_id or ""
    link = f"{APP_URL}feedback.html?cid={cid}&tid={tid}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=link))
    bot.send_message(cid, f"📉 **СВЕРКА МЕТРИК**\n\n`{link}`", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

def register_user(user, chat_id, thread_id=None, silent=False):
    try:
        # Check by ID
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        if res.data: return res.data[0]

        # Check by Username
        if user.username:
            u_low = user.username.lstrip('@').lower()
            all_t = supabase.from_("team").select("*").execute()
            for t in (all_t.data or []):
                db_u = (t.get('username') or "").lstrip('@').lower()
                if db_u == u_low:
                    supabase.from_("team").update({"telegram_id": user.id}).eq("id", t['id']).execute()
                    return t
        
        # New
        data = {"telegram_id": user.id, "username": user.username or "", "full_name": user.full_name or user.first_name, "roles": ["task"]}
        supabase.from_("team").insert(data).execute()
        if not silent:
            bot.send_message(chat_id, f"👋 Привет, {user.first_name}! Какая у тебя **Должность**?", message_thread_id=thread_id)
        return None
    except Exception as e:
        print(f"Reg err: {e}"); return None

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    tid = message.message_thread_id if message.is_topic_message else None
    for u in message.new_chat_members:
        if not u.is_bot: register_user(u, message.chat.id, tid)

@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_text(message):
    try:
        user = message.from_user
        if not user or user.is_bot: return
        tid = message.message_thread_id if message.is_topic_message else None
        
        # Phone Detection (Permissive)
        ph_match = re.findall(r'(?:\+7|8)[\s\-]?\(?7\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', message.text or "")
        is_ph = len(ph_match) > 0
        
        # 1. Identity Phase
        u_rec = register_user(user, message.chat.id, tid, silent=is_ph)
        if u_rec and not u_rec.get('position') and not is_ph:
            bot.send_message(message.chat.id, f"📝 {user.first_name}, напиши свою **Должность**.", message_thread_id=tid)

        # 2. Reply Handling
        if message.reply_to_message and message.reply_to_message.from_user.is_bot and message.text:
            b_txt = message.reply_to_message.text
            pm = re.search(r"номер телефона: `(\+7\d{10})`", b_txt)
            if pm and tid:
                ph, name = pm.group(1), message.text.strip()
                supabase.table("contacts").upsert({"name": name, "phone": ph, "thread_id": tid}, on_conflict="phone,thread_id").execute()
                bot.reply_to(message, f"✅ Контакт **{name}** ({ph}) сохранен!")
                return
            if "**Должность**" in b_txt:
                pos = message.text.strip()
                roles = ["task"]
                if any(x in pos.lower() for x in ["оператор", "камера"]): roles += ["production", "post"]
                if any(x in pos.lower() for x in ["админ", "менеджер"]): roles = ["production", "post", "task", "actor"]
                supabase.from_("team").update({"position": pos, "roles": list(set(roles))}).eq("telegram_id", user.id).execute()
                bot.reply_to(message, f"✅ Должность **{pos}** сохранена!")
                return

        # 3. Discovery (Only if Thread/Topic ID is present)
        if tid and message.text:
            # 3.1 Project Sync
            p_res = supabase.from_("clients").select("*").eq("thread_id", tid).execute()
            if not p_res.data:
                insta, name_v = "", ""
                u_m = re.search(r'instagram\.com/([^/?#\s]+)', message.text)
                at_m = re.search(r'@([\w._]+)', message.text)
                if u_m: insta = u_m.group(1)
                elif at_m: insta = at_m.group(1)
                words = [w for w in message.text.split() if w and w[0].isupper() and not w.startswith(('http', '@', '#'))]
                if words: name_v = words[0]
                
                t_name = f"{insta} | {name_v}" if insta and name_v else (insta or name_v or f"Project {tid}")
                exists = supabase.from_("clients").select("*").ilike("name", f"%{t_name}%").execute()
                if exists.data:
                    # FIX: Use 'exists' (the correct variable name)
                    supabase.from_("clients").update({"thread_id": tid}).eq("id", exists.data[0]['id']).execute()
                    bot.reply_to(message, f"🔗 Проект **{exists.data[0]['name']}** привязан к топику.")
                else:
                    supabase.from_("clients").insert({"thread_id": tid, "name": t_name}).execute()
                    bot.reply_to(message, f"🆕 Проект: **{t_name}**")

            # 3.2 Phone Discovery
            if ph_match:
                raw = ph_match[0]
                ph = raw.replace(" ","").replace("-","").replace("(","").replace(")","")
                if ph.startswith('8'): ph = '+7' + ph[1:]
                if not ph.startswith('+'): ph = '+' + ph
                
                c_ex = supabase.table("contacts").select("*").eq("phone", ph).eq("thread_id", tid).execute()
                if c_ex.data:
                    bot.reply_to(message, f"📱 Номер `{ph}` уже записан как **{c_ex.data[0]['name']}**. Хотите сменить имя? Напишите новое в ответ (Reply).")
                else:
                    after = message.text.split(raw)[-1].strip()
                    guess = " ".join([w for w in after.split() if w and w[0].isupper()][:2])
                    if guess:
                        supabase.table("contacts").insert({"name": guess, "phone": ph, "thread_id": tid}).execute()
                        bot.reply_to(message, f"✅ Контакт: **{guess}** ({ph})")
                    else:
                        bot.reply_to(message, f"📱 Вижу номер телефона: `{ph}`\nКак зовут этого клиента?")
    except Exception as e: print(f"Bot error: {e}")
