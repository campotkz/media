import os
import telebot
from telebot import types
from flask import Flask, request

# Токен в сейфе Vercel
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

@bot.message_handler(commands=['start'])
def start_command(message):
    # Создаем Inline-меню (как в твоем эталоне)
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # МАГИЯ ТОПИКОВ: отвечаем в ту же ветку, используя message_thread_id
    bot.send_message(
        message.chat.id, 
        "🦾 **GULYWOOD ERP: СИСТЕМА АКТИВИРОВАНА**\n\nИспользуйте кнопку ниже для работы с графиком:", 
        reply_markup=markup,
        message_thread_id=message.message_thread_id,
        parse_mode="Markdown"
    )

@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        bot.send_message(update.chat.id, "🎬 GULYWOOD активирован!", reply_markup=markup)
