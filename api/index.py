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

# Команда /start с поддержкой топиков (логика из твоего рабочего main.py)
@bot.message_handler(commands=['start', 'cal'])
def handle_start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ СИСТЕМУ", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # МАГИЯ ТОПИКОВ: если это сообщение в теме, отвечаем строго В ТЕМУ
    thread_id = message.message_thread_id if message.is_topic_message else None

    bot.send_message(
        message.chat.id, 
        "🦾 **СИСТЕМА АКТИВИРОВАНА**\n\nИспользуй кнопку ниже:", 
        reply_markup=markup,
        message_thread_id=thread_id, # ЭТОТ ПАРАМЕТР КРИТИЧЕН ДЛЯ ТОПИКОВ
        parse_mode="Markdown"
    )
