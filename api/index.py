import os
import telebot
from telebot import types
from flask import Flask, request

# Используем именно BOT_KEY, как ты прописал в Vercel 
TOKEN = os.environ.get('BOT_KEY')
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403

# Команда /start с поддержкой топиков (логика из твоего main.py) 
@bot.message_handler(commands=['start', 'cal'])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # Определяем ID темы (thread), чтобы ответить в ту же ветку 
    thread_id = message.message_thread_id if message.is_topic_message else None

    bot.send_message(
        message.chat.id, 
        "🦾 **GULYWOOD ERP: СИСТЕМА АКТИВИРОВАНА**\n\nИспользуй кнопку ниже для работы с графиком:", 
        reply_markup=markup,
        message_thread_id=thread_id,
        parse_mode="Markdown"
    )

# Обработка любого текста в топиках, если выключен Privacy Mode
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    thread_id = message.message_thread_id if message.is_topic_message else None
    # Если кто-то пишет в топик, бот просто напомнит про кнопку
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        "Система готова. Нажми кнопку для входа:", 
        reply_markup=markup,
        message_thread_id=thread_id
    )
