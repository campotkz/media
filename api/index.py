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
        tid = message.message_thread_id if message.is_topic_message else None
        if not tid:
            bot.reply_to(message, "❌ Эту команду нужно использовать внутри Топика (Проекта).")
            return
        
        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Goldy | Luxury`", parse_mode="Markdown")
            return

        supabase.from_("clients").update({"name": new_name}).eq("chat_id", cid).eq("thread_id", tid).execute()
        bot.reply_to(message, f"✅ Проект переименован: **{new_name}**")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}")

def ensure_project(chat_id, thread_id, chat_title, content="", message=None):
    """Ensures a project (topic) exists. Returns (category, is_new)."""
    try:
        if not thread_id: return 'media', False
        category = 'casting' if 'КАСТИНГ' in (chat_title or "").upper() else 'media'
        
        # 1. Exact Match by Thread
        p_res = supabase.from_("clients").select("*").eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
        if p_res.data:
            return p_res.data[0].get('category', category), False
        
        # 2. Not found, but let's see if we have a "discovery" candidate
        # If the user is replying with a name (Project Naming Flow)
        if message and message.reply_to_message and "Как назовем этот проект?" in (message.reply_to_message.text or ""):
            new_name = content.strip()
            # Check if this name exists in DB but without thread_id (Linking Flow)
            ex = supabase.from_("clients").select("*").ilike("name", f"%{new_name}%").execute()
            if ex.data and not ex.data[0].get('thread_id'):
                supabase.from_("clients").update({
                    "thread_id": thread_id, "chat_id": chat_id, "category": category
                }).eq("id", ex.data[0]['id']).execute()
                bot.reply_to(message, f"🔗 Проект **{ex.data[0]['name']}** привязан к этому топику.")
                return category, False
            else:
                # Create NEW
                supabase.from_("clients").insert({
                    "thread_id": thread_id, "chat_id": chat_id, "name": new_name, "category": category
                }).execute()
                bot.reply_to(message, f"✅ Проект создан: **{new_name}**")
                return category, False

        # 3. First time seeing this topic - Ask for Name
        if message:
            bot.send_message(chat_id, f"🆕 Вижу новый топик в **{category}**!\nКак назовем этот проект? (ответь на это сообщение)", message_thread_id=thread_id)
        
        # Create a temporary placeholder so we don't spam the prompt
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
