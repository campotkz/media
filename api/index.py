import telebot
from telebot import types
from flask import Flask, request

TOKEN = "8534227633:AAG8TBOLvSdfW0p7lsXFzWzmtxG5r0Xew7M"
APP_URL = "https://campotkz.github.io/media/"
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Эта функция приклеит кнопку-квадратик АВТОМАТОМ во всех новых группах
@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, persistent=True)
        btn = types.KeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        bot.send_message(update.chat.id, "GULYWOOD ERP активирован. Кнопка внизу!", reply_markup=markup)

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Forbidden', 403
