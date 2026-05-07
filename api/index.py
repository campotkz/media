import os
import telebot
import re
import json
import io
import requests
import threading
import time
import urllib.parse
import base64
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from telebot import types
from telebot.apihelper import ApiTelegramException
from supabase import create_client, Client
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image

# --- Config ---
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
APP_URL = "https://campotkz.github.io/media/"
VERCEL_URL = os.environ.get("VERCEL_URL", "media-seven-eta.vercel.app")
BASE_API_URL = f"https://{VERCEL_URL}"
MEDIA_CHANNEL_ID = os.environ.get('MEDIA_CHANNEL_ID', '-1003893557217') # Телеграм канал для хранения медиа

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY or "")
except Exception as e:
    print(f"CRITICAL: Supabase client init failed: {e}")
    supabase = None

# Version indicator for debugging
VERSION = "1.7.2 (Stateless Casting Cleanup)"

@app.after_request
def after_request(response):
    # Use assignment instead of add to avoid duplicate headers which block CORS
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

def format_casting_message(data, is_selected=False):
    """
    Generates the HTML message body for a casting application.
    """
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
        
    # Standardize video field (handle video_url and video_audition_url)
    v_url = data.get('video_url') or data.get('video_audition_url')
    if v_url:
        full_txt += f"🎥 <a href='{v_url}'>Видеовизитка</a>\n"
        
    photos = data.get('photo_urls', [])
    if isinstance(photos, str) and photos.strip():
        if photos.startswith('[') and photos.endswith(']'):
            try: photos = json.loads(photos)
            except: photos = photos.split(',')
        else:
            photos = [p.strip() for p in photos.split(',') if p.strip()]
        
    if isinstance(photos, list) and len(photos) > 3:
        full_txt += "\n🖼 <b>Дополнительные фото:</b>\n"
        for i, url in enumerate(photos[3:], 1):
            full_txt += f"• <a href='{url}'>Фото {i+3}</a>\n"
            
    return full_txt

# --- Helpers ---

def ensure_project(chat_id, thread_id, chat_title, forced_name=None):
    if not thread_id: return
    try:
        res = supabase.from_("clients").select("id").eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
        if not res.data:
            category = 'casting' if 'КАСТИНГ' in (chat_title or "").upper() else 'media'
            name = forced_name or chat_title or f"Project {thread_id}"
            supabase.from_("clients").insert({
                "chat_id": chat_id,
                "thread_id": thread_id,
                "name": name,
                "category": category,
                "is_active": True,
                "is_hidden": False
            }).execute()
    except Exception as e:
        print(f"ensure_project Error: {e}")

def optimize_url(url, width=1280):
    if not url: return url
    try:
        if "supabase.co" in url and "storage/v1/object/public" in url:
            ext = url.lower().split('.')[-1]
            if ext in ['jpg', 'jpeg', 'png', 'webp', 'tiff']:
                if '?' in url: return f"{url}&width={width}&quality=80&format=origin"
                else: return f"{url}?width={width}&quality=80&format=origin"
    except: pass
    return url

def normalize_phone(p):
    if not p: return None
    p = "".join(filter(str.isdigit, str(p)))
    if len(p) == 11 and p.startswith('8'): p = '7' + p[1:]
    return p

def normalize_insta(i):
    if not i: return None
    i = str(i).lower().strip()
    if i.startswith('@'): i = i[1:]
    if 'instagram.com/' in i: i = i.split('instagram.com/')[-1].strip('/')
    return i

_bg_executor = ThreadPoolExecutor(max_workers=3)

def auto_delete(msg, delay=10):
    if not msg: return
    def _delete():
        time.sleep(min(delay, 5))
        try: bot.delete_message(msg.chat.id, msg.message_id)
        except: pass
    try: _bg_executor.submit(_delete)
    except Exception as e: print(f"auto_delete err: {e}")

# --- Webhook Routes ---

@app.route('/api', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            print(f"Webhook Error: {e}")
        return ''
    return 'Forbidden', 403

@app.route('/api/drop', methods=['GET'])
def drop_updates():
    try:
        new_url = APP_URL.replace("campotkz.github.io/media/", "media-seven-eta.vercel.app/api")
        bot.remove_webhook()
        bot.set_webhook(url=new_url, drop_pending_updates=True)
        return jsonify({"status": "ok", "message": "Pending updates dropped, webhook reset."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['POST', 'OPTIONS'])
def submit_report():
    if request.method == 'OPTIONS': return ('', 204)
    try:
        data = request.json or {}
        chat_id, thread_id = data.get('chat_id'), data.get('thread_id')
        if not chat_id: return jsonify({'error': 'No chat_id'}), 400
        prev = supabase.table('client_feedback').select('leads_count, sales_count').eq('thread_id', thread_id or 0).order('created_at', desc=True).limit(2).execute()
        pl, ps = (prev.data[1]['leads_count'] or 0, prev.data[1]['sales_count'] or 0) if len(prev.data) > 1 else (0, 0)
        cl, cs = int(data.get('leads_count', 0)), int(data.get('sales_count', 0))
        def v(k): return str(data.get(k)) if data.get(k) else "-"
        msg = f"📊 **ОТЧЕТ ЗА МЕСЯЦ**\n\n👤 Имя: {v('client_name')}\nInst: {v('instagram')}\n\n🔥 Лиды: {cl} ({cl-pl:+})\nПродажи: {cs} ({cs-ps:+})"
        bot.send_message(chat_id, msg, message_thread_id=thread_id, parse_mode="Markdown")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send_excel', methods=['POST', 'OPTIONS'])
def send_excel():
    if request.method == 'OPTIONS': return ('', 204)
    try:
        data = request.json or {}
        project_name, base64_data = data.get('project_name'), data.get('base64_data')
        if not project_name or not base64_data: return jsonify({'error': 'Missing data'}), 400
        res = supabase.from_("clients").select("chat_id, thread_id").eq("name", project_name).execute()
        if not res.data: return jsonify({'error': 'Project not found'}), 404
        target = res.data[0]
        padding_needed = len(base64_data) % 4
        if padding_needed: base64_data += '=' * (4 - padding_needed)
        file_bytes = base64.b64decode(base64_data)
        file_io = io.BytesIO(file_bytes); file_io.name = data.get('filename', 'Export.xlsx')
        bot.send_document(target['chat_id'], file_io, message_thread_id=target['thread_id'])
        return jsonify({'status': 'ok'})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- Bot Commands ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    cid, tid = message.chat.id, message.message_thread_id or ''
    markup = types.InlineKeyboardMarkup(row_width=1)
    if tid:
        try: supabase.from_("clients").update({"is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
        except: pass
    markup.add(types.InlineKeyboardButton(text="📅 КАЛЕНДАРЬ", url=f"{APP_URL}index.html?cid={cid}&tid={tid}"))
    markup.add(types.InlineKeyboardButton(text="📊 ФИДБЕК", url=f"{APP_URL}feedback.html?cid={cid}&tid={tid}"))
    markup.add(types.InlineKeyboardButton(text="🎭 КАСТИНГ", url=f"{APP_URL}casting.html"))
    if tid:
        try:
            res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
            if res.data:
                safe_pname = urllib.parse.quote(res.data[0]['name'])
                markup.add(types.InlineKeyboardButton(text="🎯 ТОЛЬКО ЭТОТ КАСТИНГ", url=f"{APP_URL}casting.html?cid={cid}&tid={tid}&proj={safe_pname}&lock=1"))
        except: pass
    bot.send_message(cid, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=tid or None, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    cid, tid = message.chat.id, message.message_thread_id
    if tid:
        supabase.from_("clients").update({"is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
        bot.reply_to(message, "🛑 **БОТ ОСТАНОВЛЕН**", parse_mode="Markdown")
    else: bot.reply_to(message, "⚠️ Команда только для топиков.")

@bot.message_handler(commands=['cal'])
def handle_calendar(message):
    cid, tid = message.chat.id, message.message_thread_id or ''
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📅 ОТКРЫТЬ КАЛЕНДАРЬ", url=f"{APP_URL}index.html?cid={cid}&tid={tid}"))
    bot.send_message(cid, "🗓 **GULYWOOD CALENDAR**", reply_markup=markup, message_thread_id=tid or None, parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if not tid:
            return bot.reply_to(message, "❌ Эту команду нужно писать внутри конкретного топика.")

        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            return bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Проект А`", parse_mode="Markdown")
        
        # 1. Update Telegram Forum Name
        try:
            bot.edit_forum_topic(cid, tid, name=new_name)
        except Exception as e:
            print(f"TG Rename Err: {e}")

        # 2. Update Supabase
        res = supabase.from_("clients").update({"name": new_name}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        bot.reply_to(message, f"✅ Название изменено на: **{new_name}**")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}")

@bot.message_handler(commands=['archive'])
def handle_archive(message):
    cid, tid = message.chat.id, message.message_thread_id
    if not tid: return bot.reply_to(message, "❌ Только в топике.")
    supabase.from_("clients").update({"is_hidden": True, "is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
    bot.reply_to(message, "🗄️ **АРХИВИРОВАНО**")

@bot.message_handler(commands=['deleteall'])
def handle_delete_all(message):
    cid = message.chat.id
    user_id = message.from_user.id
    
    # 1. Проверка прав администратора
    try:
        member = bot.get_chat_member(cid, user_id)
        if member.status not in ['administrator', 'creator']:
            return bot.reply_to(message, "❌ У вас нет прав администратора для этой команды.")
    except Exception as e:
        return bot.reply_to(message, f"❌ Ошибка проверки прав: {e}")

    # 2. Запрос списка топиков из Supabase
    try:
        res = supabase.from_("clients").select("name, thread_id").eq("chat_id", cid).execute()
        topics = res.data or []
    except Exception as e:
        return bot.reply_to(message, f"❌ Ошибка при чтении базы данных: {e}")

    deleted_count = 0
    
    # 3. Цикл массового удаления
    for topic in topics:
        name = topic.get('name', '')
        tid = topic.get('thread_id')
        
        if not tid: continue
        
        # Исключение: Пропускаем "тестовый кастинг"
        if name.lower() == "тестовый кастинг":
            continue

        # Удаление в Telegram
        try:
            bot.delete_forum_topic(cid, tid)
        except ApiTelegramException as e:
            # Если топик уже удален или не найден, просто идем дальше
            print(f"Telegram Topic {tid} delete skip: {e.description}")
        except Exception as e:
            print(f"Unexpected Telegram Error for topic {tid}: {e}")

        # Синхронизация с БД: Удаляем запись из Supabase
        try:
            supabase.from_("clients").delete().eq("chat_id", cid).eq("thread_id", tid).execute()
            deleted_count += 1
        except Exception as e:
            print(f"Supabase Delete Error for topic {tid}: {e}")

    # 4. Финальный отчет
    bot.send_message(
        cid, 
        f"✅ **ОПЕРАЦИЯ ЗАВЕРШЕНА**\n\n"
        f"🗑 Удалено топиков: {deleted_count}\n"
        f"☁️ База Supabase очищена.\n"
        f"🛡 Оставлен только: **'тестовый кастинг'**.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['cast_link'])
def handle_specific_casting(message):
    cid, tid = message.chat.id, message.message_thread_id
    if not tid: return bot.reply_to(message, "❌ Только в топике.")
    ensure_project(cid, tid, message.chat.title)
    res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
    if res.data:
        pname = res.data[0]['name']
        link = f"{APP_URL}casting.html?cid={cid}&tid={tid}&proj={urllib.parse.quote(pname)}&lock=1"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎯 ЗАПОЛНИТЬ АНКЕТУ", url=link))
        bot.send_message(cid, f"🎯 <b>КАСТИНГ: {pname}</b>\n\n🔗 <code>{link}</code>", reply_markup=markup, message_thread_id=tid, parse_mode="HTML")

@bot.message_handler(commands=['del'])
def handle_delete(message):
    cid, tid = message.chat.id, message.message_thread_id
    if message.reply_to_message:
        txt = (message.reply_to_message.text or message.reply_to_message.caption or "")
        urls = re.findall(r'(https?://[^\s]+)', txt)
        if urls:
            for url in urls: supabase.table("project_resources").delete().eq("chat_id", cid).eq("thread_id", tid).eq("url", url).execute()
            bot.reply_to(message, "✅ Ссылки удалены из базы.")
        else: bot.reply_to(message, "❌ Ссылки не найдены.")
    else: bot.reply_to(message, "❌ Используйте ответ на сообщение.")

# --- Stateless Casting Routes ---

@app.route('/api/casting/submit_no_sb', methods=['POST', 'OPTIONS'])
def submit_no_sb():
    if request.method == 'OPTIONS': return ('', 204)
    try:
        data = request.json or {}
        cid = int(data.get('chat_id', 0))
        tid = int(data.get('thread_id', 0)) if data.get('thread_id') else None
        if not cid: return jsonify({'error': 'No chat_id'}), 400

        def v(k): return str(data.get(k) or "—").replace("<", "&lt;").replace(">", "&gt;")
        summary = (
            f"🌟 <b>НОВАЯ АНКЕТА: {v('full_name')}</b>\n"
            f"🎯 Проект: <b>{v('casting_target')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Данные:</b> {v('city')} | {v('gender')} | {v('dob')}\n"
            f"📈 Рост/Вес: {v('height_weight')} | {v('sizes')}\n"
            f"🎭 Опыт: {v('experience')}\n\n"
            f"📱 <b>Контакты:</b>\n📞 {v('phone')} | 🔗 Inst: {v('instagram')}\n\n"
            f"💰 Бюджет: {v('fee_range')}\n"
        )
        if data.get('portfolio_url'): summary += f"🔗 <a href='{v('portfolio_url')}'>Портфолио</a>\n"

        photos_b64, media_group = data.get('photos', []), []
        for i, b64 in enumerate(photos_b64[:10]):
            try:
                if ',' in b64: b64 = b64.split(',')[1]
                img_io = io.BytesIO(base64.b64decode(b64)); img_io.name = f"p{i}.jpg"
                caption = f"📸 {v('full_name')} ({v('casting_target')})" if i == 0 else None
                media_group.append(types.InputMediaPhoto(img_io, caption=caption))
            except Exception as e: print(f"Photo err: {e}")

        video_b64, video_io = data.get('video'), None
        if video_b64:
            try:
                if ',' in video_b64: video_b64 = video_b64.split(',')[1]
                video_io = io.BytesIO(base64.b64decode(video_b64)); video_io.name = "v.mp4"
            except Exception as e: print(f"Video err: {e}")

        reply_to = None
        if media_group:
            sent_media = bot.send_media_group(cid, media_group, message_thread_id=tid)
            if sent_media: reply_to = sent_media[0].message_id

        if video_io:
            sent_video = bot.send_video(cid, video_io, message_thread_id=tid, caption=f"🎥 Видео: {v('full_name')}", reply_to_message_id=reply_to)
            if not reply_to: reply_to = sent_video.message_id

        sent_msg = bot.send_message(cid, summary, message_thread_id=tid, parse_mode="HTML", reply_to_message_id=reply_to)
        return jsonify({'status': 'ok', 'msg_id': sent_msg.message_id})
    except Exception as e:
        print(f"Submit error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/casting/topics', methods=['GET', 'OPTIONS'])
def get_casting_topics():
    if request.method == 'OPTIONS': return ('', 204)
    try:
        path = os.path.join(os.path.dirname(__file__), 'casting_topics.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
        return jsonify([])
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))