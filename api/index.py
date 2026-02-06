import os
import telebot
from telebot import types
from flask import Flask, request

# Берем токен СТРОГО из Environment Variables (Сейф Vercel)
TOKEN = os.environ.get('BOT_TOKEN')
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
    else:
        return 'Error', 403

# Реагируем на всё, чтобы проверить, слышит ли бот топик
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    markup = types.InlineKeyboardMarkup()
    # Инлайн-кнопка — как в твоем main.py
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # ЛОГИКА ТОПИКОВ (message_thread_id)
    # Если это сообщение в теме, бот ответит В ЭТУ ЖЕ ТЕМУ
    thread_id = message.message_thread_id if message.is_topic_message else None

    bot.send_message(
        message.chat.id, 
        "🦾 GULYWOOD ERP в эфире!", 
        reply_markup=markup,
        message_thread_id=thread_id  # Тот самый ключ для тем
    )
