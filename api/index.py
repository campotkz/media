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

    # Handle POST
    try:
        data = request.json
        chat_id = data.get('chat_id')
        thread_id = data.get('thread_id')
        
        if not chat_id:
            return jsonify({'error': 'No chat_id'}), 400

        # 1. Fetch previous record for comparison
        prev_query = supabase.table('client_feedback')\
            .select('leads_count, sales_count')\
            .eq('thread_id', thread_id if thread_id else 0)\
            .order('created_at', desc=True)\
            .limit(2)\
            .execute()
        
        # Current is index 0 (just inserted), Previous is index 1
        prev_leads = 0
        prev_sales = 0
        if len(prev_query.data) > 1:
            prev_leads = prev_query.data[1]['leads_count'] or 0
            prev_sales = prev_query.data[1]['sales_count'] or 0
            
        # 2. Calculate Deltas
        curr_leads = int(data.get('leads_count', 0))
        curr_sales = int(data.get('sales_count', 0))
        
        diff_leads = curr_leads - prev_leads
        diff_sales = curr_sales - prev_sales
        
        leads_icon = "🟢" if diff_leads >= 0 else "🔴"
        sales_icon = "🟢" if diff_sales >= 0 else "🔴"
        
        # 3. Format Message
        def get_val(key, default='-'):
            v = data.get(key)
            return str(v) if v else default

        msg = f"""📊 **ОТЧЕТ ЗА МЕСЯЦ**
        
👤 **КОНТАКТЫ**
Имя: {get_val('client_name')}
Inst: {get_val('instagram')}
Tel: {get_val('phone')}

🔥 **ЦИФРЫ**
Лиды (Заявки): {curr_leads} (Динамика: {diff_leads:+} {leads_icon})
Продажи: {curr_sales} (Динамика: {diff_sales:+} {sales_icon})
Источник: {get_val('lead_source')}
Средний чек: {get_val('average_check')}

🎯 **КАЧЕСТВО & КОНТЕНТ**
Качество заявок: {get_val('quality_score')}/5
Реклама (Target): {get_val('ad_quality_score')}/5
Контент (Visual): {get_val('content_quality_score')}/5

🗣 **МНЕНИЯ**
Понравилось: "{get_val('favorite_content')}"
Цитаты клиентов: "{get_val('client_source_quotes')}"
Боли/Вопросы: "{get_val('customer_pain_points')}"

⚡ **ПРОЦЕССЫ**
Скорость ответа менеджера: {get_val('response_speed')}
Отдел продаж: {get_val('sales_process_rating')}

🤝 ** КОМАНДА CAMPOT**
Работа менеджера: {get_val('manager_quality_score')}/5
Общее впечатление: {get_val('agency_impression_score')}/5

🚀 **ПЛАН**
Акции/Продукты: {get_val('new_campaigns')}
Фокус месяца: {get_val('next_month_focus')}
Идеи/Пожелания: {get_val('general_suggestions')}
"""
        # 4. Send to Telegram
        bot.send_message(
            chat_id, 
            msg, 
            message_thread_id=thread_id, 
            parse_mode="Markdown"
        )
        
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
    
    # Generate Link
    link = f"{APP_URL}feedback.html?cid={chat_id}&tid={thread_id}"
    
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=link)
    markup.add(btn)
    
    bot.send_message(
        chat_id,
        f"📉 **СВЕРКА МЕТРИК**\n\nСсылка для отчета (нажмите, чтобы скопировать):\n`{link}`\n\nЗаполните, пожалуйста, данные за месяц.",
        reply_markup=markup,
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    for user in message.new_chat_members:
        if not user.is_bot:
            register_user(user, message.chat.id)

def register_user(user, chat_id, thread_id=None):
    try:
        # 1. Check if user exists by Telegram ID
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        
        if not res.data and user.username:
            # 2. Check by username if ID not found (User was seeded but ID unknown)
            res = supabase.from_("team").select("*").eq("username", user.username).execute()
            if res.data:
                # Update existing record with ID
                supabase.from_("team").update({"telegram_id": user.id}).eq("username", user.username).execute()
                return res.data[0] # Return matched user

        if not res.data:
            # 3. Truly new user
            data = {
                "telegram_id": user.id,
                "username": user.username or "",
                "full_name": user.full_name or user.first_name,
                "roles": ["task"] # Default role
            }
            supabase.from_("team").insert(data).execute()
            bot.send_message(
                chat_id, 
                f"👋 Привет, {user.first_name}! Вижу нового участника команды.\n\nНапиши, пожалуйста, свою **Должность** (например: Оператор, Монтажер, Продюсер), чтобы я добавил тебя в ERP GULYWOOD.",
                message_thread_id=thread_id
            )
            return None
        elif not res.data[0].get('position'):
            # Existing but no position
            bot.send_message(
                chat_id, 
                f"📝 {user.first_name}, напомни, пожалуйста, свою **Должность**, чтобы я правильно настроил твои доступы в ERP.",
                message_thread_id=thread_id
            )
            return res.data[0]
        
        return res.data[0]
    except Exception as e:
        print(f"Error registering user: {e}")
        return None

@bot.message_handler(content_types=['audio', 'photo', 'voice', 'video', 'document', 'text', 'location', 'contact', 'sticker'])
def handle_text(message):
    try:
        user = message.from_user
        if not user or user.is_bot: return

        # 1. Check if we need a position from this user
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        
        if not res.data:
            # First time sending a message, not caught by 'new_member'
            register_user(user, message.chat.id)
            return
            
        old_data = res.data[0]
        
        # 1.5 Handle "What is the name for this phone?" response
        # We check if the last message from bot in this chat was a phone prompt
        # but for simplicity in serverless, we check if user just sent a name and we have a pending phone in this thread
        # Actually, let's look for a name if message doesn't start with / and follows a prompt.
        # Temporary: detect if text is just a name and we have a contact with 'PENDING_NAME' phone for this thread?
        # Better: use regex for phone first.
        
        # 1.7 Phone Number Discovery
        phone_matches = re.findall(r'(?:\+7|8)[\s\-]?\(?7\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', message.text or "")
        if phone_matches and message.is_topic_message:
            phone = phone_matches[0].replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if phone.startswith('8'): phone = '+7' + phone[1:]
            if not phone.startswith('+'): phone = '+' + phone
            
            # Simple Name Extraction for same message
            name_guess = ""
            after_phone = message.text.split(phone_matches[0])[-1].strip()
            # Look for 1-2 capitalized words after phone
            words = [w for w in after_phone.split() if w and w[0].isupper()]
            if words: name_guess = " ".join(words[:2])

            existing_contact = supabase.table("contacts").select("*").eq("phone", phone).eq("thread_id", thread_id).execute()
            if not existing_contact.data:
                if name_guess:
                    supabase.table("contacts").insert({"name": name_guess, "phone": phone, "thread_id": thread_id}).execute()
                    bot.reply_to(message, f"✅ Обнаружил контакт: **{name_guess}** ({phone}).")
                else:
                    bot.reply_to(message, f"📱 Вижу номер телефона: `{phone}`\n\nКак зовут этого клиента за этим номером? (Ответьте Reply на это сообщение)")
                    return

        # 2. Project (Client) Discovery
        if message.is_topic_message:
            existing = supabase.from_("clients").select("id").eq("thread_id", thread_id).execute()
            if not existing.data:
                # NEW TOPIC DETECTED - Try to find Name: Inst | Client Name
                insta_handle = ""
                url_match = re.search(r'instagram\.com/([^/?#\s]+)', message.text or "")
                at_match = re.search(r'@([\w._]+)', message.text or "")
                if url_match: insta_handle = url_match.group(1)
                elif at_match: insta_handle = at_match.group(1)

                name_val = ""
                # Look for capitalized words that aren't the handle
                words = [w for w in (message.text or "").split() if w and w[0].isupper() and not w.startswith(('http', '@', '#'))]
                if words: name_val = words[0]

                proj_name = f"Topic {thread_id}"
                if insta_handle and name_val: proj_name = f"{insta_handle} | {name_val}"
                elif insta_handle: proj_name = insta_handle
                elif name_val: proj_name = name_val

                supabase.from_("clients").insert({"thread_id": thread_id, "name": proj_name}).execute()
                bot.reply_to(message, f"🆕 Проект зарегистрирован: **{proj_name}**")
                
    except Exception as e:
        print(f"Auto-discovery error: {e}")
