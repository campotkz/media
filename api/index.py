import telebot
from telebot import types
from flask import Flask, request

TOKEN = "8534227633:AAG8TBOLvSdfW0p7lsXFzWzmtxG5r0Xew7M"
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
    return "GULYWOOD Engine is Running"

# Исправленная функция для ГРУПП
@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        # Используем InlineKeyboardMarkup вместо ReplyKeyboardMarkup
        markup = types.InlineKeyboardMarkup()
        # Тип кнопки тоже меняем на InlineKeyboardButton
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        
        bot.send_message(
            update.chat.id, 
            "🎬 GULYWOOD ERP активирован!\nНажмите на кнопку ниже, чтобы открыть график съемок:", 
            reply_markup=markup
        )

# Исправленная команда /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.send_message(message.chat.id, "Для работы с GULYWOOD используйте кнопку:", reply_markup=markup)
