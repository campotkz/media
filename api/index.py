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

# Команда /start - теперь с поддержкой топиков
@bot.message_handler(commands=['start'])
def start_command(message):
    # Создаем инлайн-меню, как в твоем файле main.py
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # Ключевой момент: передаем message_thread_id
    bot.send_message(
        message.chat.id, 
        "🦾 **GULYWOOD ERP: СИСТЕМА АКТИВИРОВАНА**\n\nИспользуй кнопку ниже для работы с графиком:", 
        reply_markup=markup,
        message_thread_id=message.message_thread_id, # Чтобы кнопка была в топике
        parse_mode="Markdown"
    )
