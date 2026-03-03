import os
import telebot
import re
from telebot import types
from telebot.apihelper import ApiTelegramException
from flask import Flask, request, jsonify
from supabase import create_client, Client
import base64
import io
import json
from datetime import datetime
import binascii
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.parse
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# --- Config ---
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_KEY') 
APP_URL = "https://campotkz.github.io/media/"
VERCEL_URL = os.environ.get("VERCEL_URL", "media-seven-eta.vercel.app")
BASE_API_URL = f"https://{VERCEL_URL}"
# ID канала для хранения медиа (замените на свой или задайте в env)
MEDIA_CHANNEL_ID = os.environ.get('MEDIA_CHANNEL_ID', '-3893557217') 

# Max Base64 length equivalent to 50MB
MAX_BASE64_LENGTH = 50 * 1024 * 1024 * 4 // 3

# --- AUTO-MIGRATION CONFIG ---
SUPABASE_PAT = os.environ.get('SUPABASE_PAT', "7cc5f46c-43e4-409c-91af-b71cb62a7f1b") 
PROJECT_REF = "waekzofajzqcpoeldhkt"

def ensure_casting_schema_update():
    sql = "ALTER TABLE public.casting_applications ADD COLUMN IF NOT EXISTS media_message_ids jsonb;"
    try:
        url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/query"
        headers = {"Authorization": f"Bearer {SUPABASE_PAT}", "Content-Type": "application/json"}
        payload = {"query": sql}
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code in [200, 201]:
            print("✅ AUTO-MIGRATION SUCCESS: Table 'casting_applications' updated.")
    except Exception as e:
        print(f"❌ AUTO-MIGRATION ERROR: {e}")

if SUPABASE_PAT and len(SUPABASE_PAT) > 10:
    threading.Thread(target=ensure_casting_schema_update).start()

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VERSION = "1.6.1 (Conflict Fixed)"

# --- Helpers & Logic ---

def format_casting_message(data, is_selected=False):
    def v(k): return str(data.get(k) or "—").replace("<", "&lt;").replace(">", "&gt;")
    header_prefix = "🟢 SELECTED: " if is_selected else ""
    full_txt = (
        f"{header_prefix}🌟 <b>НОВАЯ АНКЕТА: {v('full_name')}</b>\n"
        f"🎯 Кастинг: <b>{v('casting_target')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Личные данные:</b>\n"
        f"📍 {v('city')} | {v('gender')}\n"
        f"🎂 Возраст: <b>{v('dob')}</b>\n"
        f"🎭 Внешность: {v('nationality')}\n\n"
        f"📏 <b>Параметры:</b>\n"
        f"📈 Рост/Вес: <b>{v('height_weight')}</b>\n"
        f"👟 Размеры: <b>{v('sizes')}</b>\n\n"
        f"📱 <b>Контакты:</b>\n"
        f"🔗 Inst: {v('instagram')}\n"
        f"📞 WhatsApp: {v('phone')}\n\n"
        f"💡 <b>Опыт:</b>\n{v('experience')}\n\n"
        f"🎭 <b>Навыки:</b>\n{v('skills')}\n\n"
        f"💎 <b>Финансы и Прочее:</b>\n"
        f"💰 Бюджет: {v('fee_range')}\n"
        f"👙 Белье: {v('underwear_ok')} | Массовка: {v('extras_ok')}\n"
    )
    if data.get('portfolio_url'):
        full_txt += f"\n🔗 <a href='{data.get('portfolio_url')}'>Портфолио / Ссылка</a>\n"

    photos = data.get('photo_urls') or []
    video = data.get('video_audition_url')
    if photos or video:
        full_txt += f"\n🖼️ <b>МЕДИА-ФАЙЛЫ:</b>\n"
        if isinstance(photos, list):
            for i, p_url in enumerate(photos):
                full_txt += f"• <a href='{p_url}'>Фото {i+1}</a>\n"
        if video:
            full_txt += f"• <a href='{video}'>Видео-визитка</a>\n"
    return full_txt

def optimize_url(url, width=800):
    if not url: return url
    if "supabase.co" in url and "storage/v1/object/public" in url:
        ext = url.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg', 'png', 'webp']:
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}width={width}&quality=80&format=origin"
    return url

def _tg_retry(fn, *args, **kwargs):
    attempts = 0
    while attempts < 5:
        try:
            return fn(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = e.result_json.get('parameters', {}).get('retry_after', 1)
                time.sleep(retry_after + 1)
                attempts += 1
            else: raise
        except Exception: raise
    return None

def _normalize_url_list(value):
    if not value: return []
    if isinstance(value, list): return [v for v in value if isinstance(v, str) and v.startswith("http")]
    if isinstance(value, str):
        if value.startswith('['):
            try:
                data = json.loads(value)
                return [v for v in data if isinstance(v, str) and v.startswith("http")]
            except: pass
        return [value] if value.startswith("http") else []
    return []

# --- Media Offloading (Fixed Conflict) ---

def offload_media_to_telegram(app_id, data):
    try:
        target_channel_id = MEDIA_CHANNEL_ID
        if not target_channel_id:
            print("⚠️ MEDIA_CHANNEL_ID not set. Skipping offload.")
            return data

        photos = _normalize_url_list(data.get('photo_urls'))
        video = data.get('video_audition_url')
        new_photos = []

        if photos:
            for url in photos:
                if 'supabase' in url:
                    try:
                        opt_url = optimize_url(url, width=800)
                        msg = _tg_retry(bot.send_photo, target_channel_id, opt_url, disable_notification=True)
                        if msg and msg.photo:
                            file_id = msg.photo[-1].file_id
                            new_photos.append(f"tg://{file_id}")
                            # Cleanup Supabase
                            if '/casting_media/' in url:
                                rel_path = url.split('/casting_media/')[1].split('?')[0]
                                supabase.storage.from_('casting_media').remove([rel_path])
                        else: new_photos.append(url)
                    except: new_photos.append(url)
                else: new_photos.append(url)

        new_video = video
        if video and 'supabase' in video:
            try:
                msg = _tg_retry(bot.send_video, target_channel_id, video, disable_notification=True)
                if msg and msg.video:
                    new_video = f"tg://{msg.video.file_id}"
                    if '/casting_media/' in video:
                        rel_path = video.split('/casting_media/')[1].split('?')[0]
                        supabase.storage.from_('casting_media').remove([rel_path])
            except: pass

        # Update DB
        data['photo_urls'] = ",".join(new_photos) if new_photos else None
        data['video_audition_url'] = new_video
        if app_id:
            supabase.table('casting_applications').update({
                'photo_urls': data['photo_urls'],
                'video_audition_url': new_video
            }).eq('id', app_id).execute()

    except Exception as e:
        print(f"⚠️ Offload media error: {e}")
    return data

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    cid, tid = message.chat.id, message.message_thread_id
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    cal_url = f"{APP_URL}index.html?cid={cid}&tid={tid or ''}"
    markup.add(types.InlineKeyboardButton("📅 КАЛЕНДАРЬ", url=cal_url))
    markup.add(types.InlineKeyboardButton("📊 ФИДБЕК", url=f"{APP_URL}feedback.html?cid={cid}&tid={tid or ''}"))
    markup.add(types.InlineKeyboardButton("🎭 КАСТИНГ", url=f"{APP_URL}casting.html"))
    
    bot.send_message(cid, f"🦾 **GULYWOOD ERP v{VERSION}**", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def handle_add_command(message):
    cid, tid = message.chat.id, message.message_thread_id
    if not tid:
        bot.reply_to(message, "❌ Команда только для топиков.")
        return

    # Если это ответ на анкету - запускаем процесс обновления медиа
    if message.reply_to_message:
        target_reply = message.reply_to_message
        if "АНКЕТА:" in (target_reply.text or target_reply.caption or ""):
            process_manual_media_update(message, target_reply)
            return

    # Иначе - меню добавления
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 Актер", callback_data=f"add_cat:actors:{tid}"),
        types.InlineKeyboardButton("🛠 Сотрудник", callback_data=f"add_cat:crew:{tid}"),
        types.InlineKeyboardButton("📍 Локация", callback_data=f"add_cat:locs:{tid}"),
        types.InlineKeyboardButton("🔗 Ссылка", callback_data=f"add_cat:links:{tid}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="add_cancel")
    )
    bot.send_message(cid, "➕ **ЧТО ДОБАВИТЬ?**", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

# ... (Остальные функции генерации DOCX, очистки и т.д. остаются без изменений) ...

def process_manual_media_update(source_msg, application_msg):
    try:
        cid, tid = source_msg.chat.id, source_msg.message_thread_id
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", application_msg.message_id).execute()
        if not res.data:
            bot.send_message(cid, "❌ Анкета не найдена в базе.", message_thread_id=tid)
            return
        
        app_data = res.data[0]
        # Логика загрузки и апдейта...
        # [Здесь ваша логика process_manual_media_update]
        bot.reply_to(source_msg, "⏳ Обработка медиа...")
    except Exception as e:
        print(f"Err: {e}")

# --- Webhook setup ---
@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))