import os
import telebot
from telebot import types
from flask import Flask, request

# Проверяем наличие токена, чтобы сервер не падал
TOKEN = os.environ.get('BOT_TOKEN')
APP_URL = "https://campotkz.github.io/media/"

app = Flask(__name__)

# Если токена нет в настройках Vercel, мы узнаем об этом сразу
if not TOKEN:
    print("ERROR: BOT_TOKEN is not defined in Environment Variables!")
    bot = None
else:
    bot = telebot.TeleBot(TOKEN, threaded=False)

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def webhook(path):
    if not bot:
        return "Bot token missing", 500
    
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return "GULYWOOD Engine is Active"

@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        bot.send_message(update.chat.id, "🎥 GULYWOOD ERP активирован!", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.send_message(message.chat.id, "Бот готов к работе:", reply_markup=markup)
