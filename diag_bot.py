import os
import telebot

BOT_KEY = os.environ.get('BOT_KEY')
MEDIA_CHANNEL_ID = '-1003893557217'

bot = telebot.TeleBot(BOT_KEY)

try:
    me = bot.get_me()
    print(f"Bot Name: {me.first_name} (@{me.username})")
    
    msg = bot.send_message(MEDIA_CHANNEL_ID, "🛠 Diagnostics: Bot is trying to send a test message.")
    print(f"✅ Success: Message sent to storage channel! ID: {msg.message_id}")
    
except Exception as e:
    print(f"❌ Error during diagnostics: {e}")
