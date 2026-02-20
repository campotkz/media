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
        # CORS preflight
        response = app.make_response('')
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    try:
        data = request.json
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        if not chat_id: return jsonify({'error': 'No chat_id'}), 400
        prev_query = supabase.table('client_feedback').select('leads_count, sales_count').eq('thread_id', thread_id if thread_id else 0).order('created_at', desc=True).limit(2).execute()
        prev_leads, prev_sales = 0, 0
        if len(prev_query.data) > 1:
            prev_leads = prev_query.data[1]['leads_count'] or 0
            prev_sales = prev_query.data[1]['sales_count'] or 0
        curr_leads = int(data.get('leads_count', 0))
        curr_sales = int(data.get('sales_count', 0))
        diff_leads = curr_leads - prev_leads
        diff_sales = curr_sales - prev_sales
        leads_icon = "🟢" if diff_leads >= 0 else "🔴"
        sales_icon = "🟢" if diff_sales >= 0 else "🔴"
        def get_val(key, default='-'):
            v = data.get(key)
            return str(v) if v else default
        msg = f"📊 **ОТЧЕТ ЗА МЕСЯЦ**\n\n👤 **КОНТАКТЫ**\nИмя: {get_val('client_name')}\nInst: {get_val('instagram')}\nTel: {get_val('phone')}\n\n🔥 **ЦИФРЫ**\nЛиды (Заявки): {curr_leads} (Динамика: {diff_leads:+} {leads_icon})\nПродажи: {curr_sales} (Динамика: {diff_sales:+} {sales_icon})\nИсточник: {get_val('lead_source')}\nСредний чек: {get_val('average_check')}\n\n🎯 **КАЧЕСТВО & КОНТЕНТ**\nКачество заявок: {get_val('quality_score')}/5\nРеклама (Target): {get_val('ad_quality_score')}/5\nКонтент (Visual): {get_val('content_quality_score')}/5\n\n🗣 **МНЕНИЯ**\nПонравилось: \"{get_val('favorite_content')}\"\nЦитаты клиентов: \"{get_val('client_source_quotes')}\"\nБоли/Вопросы: \"{get_val('customer_pain_points')}\"\n\n⚡ **ПРОЦЕССЫ**\nСкорость ответа менеджера: {get_val('response_speed')}\nОтдел продаж: {get_val('sales_process_rating')}\n\n🤝 ** КОМАНДА CAMPOT**\nРабота менеджера: {get_val('manager_quality_score')}/5\nОбщее впечатление: {get_val('agency_impression_score')}/5\n\n🚀 **ПЛАН**\nАкции/Продукты: {get_val('new_campaigns')}\nФокус месяца: {get_val('next_month_focus')}\nИдеи/Пожелания: {get_val('general_suggestions')}"
        bot.send_message(chat_id, msg, message_thread_id=thread_id, parse_mode="Markdown")
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@bot.message_handler(commands=['start', 'cal'])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", url=APP_URL)
    markup.add(btn)
    thread_id = message.message_thread_id if message.is_topic_message else None
    bot.send_message(message.chat.id, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=thread_id, parse_mode="Markdown")

@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    chat_id = message.chat.id
    thread_id = message.message_thread_id if message.is_topic_message else ""
    link = f"{APP_URL}feedback.html?cid={chat_id}&tid={thread_id}"
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=link)
    markup.add(btn)
    bot.send_message(chat_id, f"📉 **СВЕРКА МЕТРИК**\n\nСсылка для отчета (нажмите, чтобы скопировать):\n`{link}`\n\nЗаполните, пожалуйста, данные за месяц.", reply_markup=markup, message_thread_id=message.message_thread_id, parse_mode="Markdown")

def register_user(user, chat_id, thread_id=None):
    try:
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        if not res.data and user.username:
            clean_uname = user.username.lstrip('@').lower()
            all_team = supabase.from_("team").select("*").execute()
            match = next((t for t in all_team.data if t.get('username', '').lstrip('@').lower() == clean_uname), None)
            if match:
                supabase.from_("team").update({"telegram_id": user.id}).eq("id", match['id']).execute()
                return match
        if not res.data:
            data = {"telegram_id": user.id, "username": user.username or "", "full_name": user.full_name or user.first_name, "roles": ["task"]}
            supabase.from_("team").insert(data).execute()
            bot.send_message(chat_id, f"👋 Привет, {user.first_name}! Вижу нового участника.\nНапиши свою **Должность**, чтобы я добавил тебя в ERP.", message_thread_id=thread_id)
            return None
        rec = res.data[0]
        if not rec.get('position'):
            bot.send_message(chat_id, f"📝 {user.first_name}, напиши свою **Должность** для ERP.", message_thread_id=thread_id)
            return rec
        return rec
    except Exception as e:
        print(f"Reg error: {e}")
        return None

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    thread_id = message.message_thread_id if message.is_topic_message else None
    for user in message.new_chat_members:
        if not user.is_bot: register_user(user, message.chat.id, thread_id)

@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_text(message):
    try:
        user = message.from_user
        if not user or user.is_bot: return
        thread_id = message.message_thread_id if message.is_topic_message else None
        user_record = register_user(user, message.chat.id, thread_id)
        if message.reply_to_message and message.reply_to_message.from_user.is_bot and message.text and not message.text.startswith('/'):
            bot_text = message.reply_to_message.text
            phone_m = re.search(r"Вижу номер телефона: `(\+7\d{10})`", bot_text)
            if phone_m and thread_id:
                phone, name = phone_m.group(1), message.text.strip()
                supabase.table("contacts").upsert({"name": name, "phone": phone, "thread_id": thread_id}, on_conflict="phone,thread_id").execute()
                bot.reply_to(message, f"✅ Имя контакта обновлено: **{name}** ({phone})")
                return
            if "Напиши свою Должность" in bot_text:
                pos = message.text.strip()
                roles = ["task"]
                p_low = pos.lower()
                if any(k in p_low for k in ["оператор", "камера"]): roles += ["production", "post"]
                if any(k in p_low for k in ["монтаж", "motion", "дизайн", "vfx"]): roles += ["post"]
                if any(k in p_low for k in ["актер", "актриса", "модель"]): roles += ["actor"]
                if any(k in p_low for k in ["менеджер", "руководитель", "продюсер", "админ"]): roles = ["production", "post", "task", "actor"]
                supabase.from_("team").update({"position": pos, "roles": list(set(roles))}).eq("telegram_id", user.id).execute()
                bot.reply_to(message, f"✅ Должность **{pos}** сохранена!")
                return
        if message.is_topic_message and message.text:
            # 3.1 Project Discovery / Linking
            res_p = supabase.from_("clients").select("*").eq("thread_id", thread_id).execute()
            if not res_p.data:
                insta, name_val = "", ""
                u_link = re.search(r'instagram\.com/([^/?#\s]+)', message.text)
                a_mention = re.search(r'@([\w._]+)', message.text)
                if u_link: insta = u_link.group(1)
                elif a_mention: insta = a_mention.group(1)
                words = [w for w in message.text.split() if w and w[0].isupper() and not w.startswith(('http', '@', '#'))]
                if words: name_val = words[0]
                
                # Check for existing project with this name to link thread_id
                target_name = ""
                if insta and name_val: target_name = f"{insta} | {name_val}"
                elif insta: target_name = insta
                elif name_val: target_name = name_val
                
                if target_name:
                    existing = supabase.from_("clients").select("*").ilike("name", f"%{target_name}%").execute()
                    if existing.data:
                        # Link thread_id to the most similar existing project
                        supabase.from_("clients").update({"thread_id": thread_id}).eq("id", existing.data[0]['id']).execute()
                        bot.reply_to(message, f"🔗 Связал проект **{existing.data[0]['name']}** с этим топиком.")
                    else:
                        supabase.from_("clients").insert({"thread_id": thread_id, "name": target_name}).execute()
                        bot.reply_to(message, f"🆕 Проект зарегистрирован: **{target_name}**")
                else:
                    supabase.from_("clients").insert({"thread_id": thread_id, "name": f"Topic {thread_id}"}).execute()

            # 3.2 Phone Discovery
            phone_matches = re.findall(r'(?:\+7|8)[\s\-]?\(?7\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', message.text)
            if phone_matches:
                raw_phone = phone_matches[0]
                phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                if phone.startswith('8'): phone = '+7' + phone[1:]
                if not phone.startswith('+'): phone = '+' + phone
                name_hint = ""
                after = message.text.split(raw_phone)[-1].strip()
                hint_w = [w for w in after.split() if w and w[0].isupper()]
                if hint_w: name_hint = " ".join(hint_w[:2])
                exists = supabase.table("contacts").select("*").eq("phone", phone).eq("thread_id", thread_id).execute()
                if exists.data:
                    old_name = exists.data[0]['name']
                    bot.reply_to(message, f"📱 Номер `{phone}` уже записан как **{old_name}**. Хотите переименовать? Напишите новое имя в ответ (Reply).")
                else:
                    if name_hint:
                        supabase.table("contacts").insert({"name": name_hint, "phone": phone, "thread_id": thread_id}).execute()
                        bot.reply_to(message, f"✅ Обнаружил контакт: **{name_hint}** ({phone})")
                    else:
                        bot.reply_to(message, f"📱 Вижу номер телефона: `{phone}`\nНапишите имя клиента в ответ (Reply).")
    except Exception as e:
        print(f"Bot error: {e}")
