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

# Реагируем на ЛЮБОЕ сообщение в группе (чтобы точно проверить связь)
@bot.message_handler(func=lambda message: True)
def work_in_group(message):
    markup = types.InlineKeyboardMarkup()
    # Inline-кнопка — ЕДИНСТВЕННЫЙ вариант для Mini App в группах
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.reply_to(message, "GULYWOOD ERP готов к работе. Жми на кнопку под этим сообщением:", reply_markup=markup)
