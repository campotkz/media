import os
import telebot
from telebot import types
from flask import Flask, request

# Берем токен из Environment Variables на Vercel
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
    # Как в твоем main.py: создаем Инлайн-кнопку
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
    markup.add(btn)

    # МАГИЯ ТОПИКОВ: отвечаем строго в ту ветку, где написали команду
    bot.send_message(
        message.chat.id, 
        "🦾 **GULYWOOD ERP: СИСТЕМА АКТИВИРОВАНА**\n\nНажми кнопку ниже для работы с графиком:", 
        reply_markup=markup,
        message_thread_id=message.message_thread_id, # ЭТО ДЛЯ ТОПИКОВ
        parse_mode="Markdown"
    )

@bot.my_chat_member_handler()
def on_added(update):
    if update.new_chat_member.status in ["member", "administrator"]:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="🎬 ОТКРЫТЬ GULYWOOD", web_app=types.WebAppInfo(url=APP_URL))
        markup.add(btn)
        bot.send_message(update.chat.id, "🎬 GULYWOOD активирован в этой группе!", reply_markup=markup)
