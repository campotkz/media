import os
import telebot
from telebot import types
from flask import Flask, request

TOKEN = os.environ.get('BOT_TOKEN')
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/api', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return ''

# Обрабатываем команду /start или любое слово
@bot.message_handler(func=lambda message: True)
def send_calendar_button(message):
    # 1. Создаем Inline-кнопку (она разрешена в группах для Mini App)
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    
    # 2. Определяем ID топика (thread_id), если он есть
    thread_id = message.message_thread_id if message.is_topic_message else None

    # 3. Отвечаем именно в тот топик, откуда пришел запрос
    bot.send_message(
        message.chat.id, 
        "График съемок GULYWOOD ERP готов к работе:", 
        reply_markup=markup,
        message_thread_id=thread_id  # Тот самый ключ для топиков
    )
