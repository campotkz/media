import os
import telebot
from telebot import types
from flask import Flask, request

# Теперь токен берется из настроек сервера, а не из кода!
TOKEN = os.environ.get('BOT_TOKEN')
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def webhook(path):
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return "GULYWOOD is Secured"

@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        bot.send_message(update.chat.id, "🎥 GULYWOOD ERP активирован!\nГрафик съемок по кнопке ниже:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.send_message(message.chat.id, "Запуск GULYWOOD ERP:", reply_markup=markup)
