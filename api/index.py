import telebot
from telebot import types
from flask import Flask, request

# Данные GULYWOOD
TOKEN = "8534227633:AAG8TBOLvSdfW0p7lsXFzWzmtxG5r0Xew7M"
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Обрабатываем и / и /api, чтобы наверняка
@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def webhook(path):
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return "GULYWOOD is Online"

# Эта функция сработает, когда ты добавишь бота в группу
@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        # Используем Inline-кнопку (только она работает в группах!)
        markup = types.InlineKeyboardMarkup()
        # Явно создаем объект WebAppInfo
        web_app_info = types.WebAppInfo(url=APP_URL)
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=web_app_info)
        markup.add(btn)
        
        bot.send_message(
            update.chat.id, 
            "🎥 GULYWOOD ERP активирован для этой группы!\nНажмите кнопку ниже, чтобы открыть график:", 
            reply_markup=markup
        )

# Команда старт для проверки
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.send_message(message.chat.id, "Запуск GULYWOOD ERP:", reply_markup=markup)
