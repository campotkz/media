import os
import telebot
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

🎯 **КАЧЕСТВО**
Оценка: {get_val('quality_score')}/5
Цитаты клиентов:
"{get_val('client_source_quotes')}"
Боли/Вопросы:
"{get_val('customer_pain_points')}"

⚡ **ПРОЦЕССЫ**
Скорость ответа: {get_val('response_speed')}
Узнаваемость (Offline): {get_val('brand_awareness_offline')}

📢 **КОНТЕНТ**
Понравилось: {get_val('favorite_content')}
Не хватает: {get_val('missing_content_needs')}
Ощущение охвата: {get_val('reach_score')}/5

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
