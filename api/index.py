import telebot
from telebot import types
from flask import Flask, request

# Твои данные
TOKEN = "8534227633:AAG8TBOLvSdfW0p7lsXFzWzmtxG5r0Xew7M"
APP_URL = "https://campotkz.github.io/media/"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# 1. АВТО-КНОПКА: Срабатывает, когда ты добавляешь бота в любую группу
@bot.my_chat_member_handler()
def on_added_to_group(update):
    # Проверяем, что бота именно добавили (статус member или administrator)
    if update.new_chat_member.status in ["member", "administrator"]:
        chat_id = update.chat.id
        
        # Создаем ту самую клавиатуру с "квадратиком"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, persistent=True)
        web_app = types.WebAppInfo(url=APP_URL)
        btn = types.KeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=web_app)
        markup.add(btn)
        
        # Отправляем приветствие и приклеиваем меню
        bot.send_message(
            chat_id, 
            "🎥 GULYWOOD ERP активирован!\nКнопка вызова календаря теперь всегда внизу клавиатуры.", 
            reply_markup=markup
        )

# 2. КОМАНДЫ: Реакция на /start или /cal
@bot.message_handler(commands=['start', 'cal'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, persistent=True)
    btn = types.KeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)
    bot.send_message(message.chat.id, "Используйте кнопку ниже для работы с графиком:", reply_markup=markup)

# 3. WEBHOOK: Прием сигналов от Telegram через Vercel
@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Forbidden', 403

# Для проверки в браузере
@app.route('/')
def index():
    return "GULYWOOD Bot is Running"
