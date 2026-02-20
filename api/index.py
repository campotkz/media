import os
import telebot
import re
from telebot import types
from flask import Flask, request, jsonify
from supabase import create_client, Client

# Config
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = "sb_publishable_XVByRUkaKbM-11ChwOd2Aw_y24CSb4V" # Public key is fine due to RLS
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
        p_leads, p_sales = 0, 0
        if len(prev_query.data) > 1:
            p_leads, p_sales = prev_query.data[1]['leads_count'] or 0, prev_query.data[1]['sales_count'] or 0
        c_leads, c_sales = int(data.get('leads_count', 0)), int(data.get('sales_count', 0))
        d_l, d_s = c_leads - p_leads, c_sales - p_sales
        l_i, s_i = ("🟢" if d_l >= 0 else "🔴"), ("🟢" if d_s >= 0 else "🔴")
        def v(k): return str(data.get(k)) if data.get(k) else "-"
        msg = f"📊 **ОТЧЕТ ЗА МЕСЯЦ**\n\n👤 **КОНТАКТЫ**\nИмя: {v('client_name')}\nInst: {v('instagram')}\nTel: {v('phone')}\n\n🔥 **ЦИФРЫ**\nЛиды: {c_leads}\nПродажи: {c_sales}\n\n🤝 **КОМАНДА CAMPOT**"
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
        # 1. Direct ID match
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        if res.data: return res.data[0]

        # 2. Robust Username match
        if user.username:
            u_low = user.username.lstrip('@').lower()
            all_t = supabase.from_("team").select("*").execute()
            for t in (all_t.data or []):
                db_u = (t.get('username') or "").lstrip('@').lower()
                if db_u == u_low and u_low:
                    # Found match! Update ID and return
                    supabase.from_("team").update({"telegram_id": user.id}).eq("id", t['id']).execute()
                    return t
        
        # 3. New User or ID unknown
        data = {"telegram_id": user.id, "username": user.username or "", "full_name": user.full_name or user.first_name, "roles": ["task"]}
        supabase.from_("team").insert(data).execute()
        if not silent:
            bot.send_message(chat_id, f"👋 Привет, {user.first_name}!\nЯ привязал твой аккаунт. Скажи, какая у тебя **Должность** (например: Менеджер, Оператор)?", message_thread_id=thread_id)
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

        # 1. Identity Check
        is_p = bool(re.search(r'(?:\+7|8)[\s\-]?\(?7\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', message.text or ""))
        u_rec = register_user(user, message.chat.id, tid, silent=is_p)
        
        # If user has no position and it's NOT a phone message, prompt
        if u_rec and not u_rec.get('position') and not is_p:
            bot.send_message(message.chat.id, f"📝 {user.first_name}, напомни свою **Должность** для ERP.", message_thread_id=tid)

        # 2. Handle Replies
        if message.reply_to_message and message.reply_to_message.from_user.is_bot and message.text and not message.text.startswith('/'):
            b_text = message.reply_to_message.text
            ph_m = re.search(r"номер телефона: `(\+7\d{10})`", b_text)
            if ph_m and tid:
                ph, name = ph_m.group(1), message.text.strip()
                supabase.table("contacts").upsert({"name": name, "phone": ph, "thread_id": tid}, on_conflict="phone,thread_id").execute()
                bot.reply_to(message, f"✅ Контакт **{name}** ({ph}) сохранен!")
                return
            if "**Должность**" in b_text:
                pos = message.text.strip()
                roles = ["task"]
                if any(x in pos.lower() for x in ["оператор", "камера"]): roles += ["production", "post"]
                if any(x in pos.lower() for x in ["монтаж", "дизайн", "edit"]): roles += ["post"]
                if any(x in pos.lower() for x in ["админ", "мендж", "прод"]): roles = ["production", "post", "task", "actor"]
                supabase.from_("team").update({"position": pos, "roles": list(set(roles))}).eq("telegram_id", user.id).execute()
                bot.reply_to(message, f"✅ Должность **{pos}** сохранена!")
                return

        # 3. Discovery (Only in Topics)
        if message.is_topic_message and message.text:
            # 3.1 Project Discovery
            p_res = supabase.from_("clients").select("*").eq("thread_id", tid).execute()
            if not p_res.data:
                insta, name_v = "", ""
                u_m = re.search(r'instagram\.com/([^/?#\s]+)', message.text)
                at_m = re.search(r'@([\w._]+)', message.text)
                if u_m: insta = u_m.group(1)
                elif at_m: insta = at_m.group(1)
                words = [w for w in message.text.split() if w and w[0].isupper() and not w.startswith(('http', '@', '#'))]
                if words: name_v = words[0]
                
                t_name = f"{insta} | {name_v}" if insta and name_v else (insta or name_v or f"Topic {tid}")
                exists = supabase.from_("clients").select("*").ilike("name", f"%{t_name}%").execute()
                if exists.data:
                    supabase.from_("clients").update({"thread_id": tid}).eq("id", exists.data[0]['id']).execute()
                    bot.reply_to(message, f"🔗 Проект **{exists.data[0]['name']}** привязан к топику.")
                else:
                    supabase.from_("clients").insert({"thread_id": tid, "name": t_name}).execute()
                    bot.reply_to(message, f"🆕 Проект зарегистрирован: **{t_name}**")

            # 3.2 Phone Discovery
            ph_match = re.findall(r'(?:\+7|8)[\s\-]?\(?7\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', message.text)
            if ph_match:
                raw = ph_match[0]
                phone = raw.replace(" ","").replace("-","").replace("(","").replace(")","")
                if phone.startswith('8'): phone = '+7' + phone[1:]
                if not phone.startswith('+'): phone = '+' + phone
                
                c_ex = supabase.table("contacts").select("*").eq("phone", phone).eq("thread_id", tid).execute()
                if c_ex.data:
                    bot.reply_to(message, f"📱 Номер `{phone}` уже записан как **{c_ex.data[0]['name']}**. Хотите сменить имя? Напишите новое в ответ (Reply).")
                else:
                    after = message.text.split(raw)[-1].strip()
                    guess = " ".join([w for w in after.split() if w and w[0].isupper()][:2])
                    if guess:
                        supabase.table("contacts").insert({"name": guess, "phone": phone, "thread_id": tid}).execute()
                        bot.reply_to(message, f"✅ Контакт: **{guess}** ({phone})")
                    else:
                        bot.reply_to(message, f"📱 Вижу номер: `{phone}`\nКак зовут этого клиента?")
    except Exception as e: print(f"Bot error: {e}")
