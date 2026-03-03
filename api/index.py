import os
import telebot
import re
import json
import io
import requests
import threading
import time
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from telebot import types
from telebot.apihelper import ApiTelegramException
from supabase import create_client, Client
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- Config ---
TOKEN = os.environ.get('BOT_KEY')
SUPABASE_URL = "https://waekzofajzqcpoeldhkt.supabase.co"
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
APP_URL = "https://campotkz.github.io/media/"
VERCEL_URL = os.environ.get("VERCEL_URL", "media-seven-eta.vercel.app")
BASE_API_URL = f"https://{VERCEL_URL}"
MEDIA_CHANNEL_ID = os.environ.get('MEDIA_CHANNEL_ID', '-1001893557217') # Убедитесь, что ID верный

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VERSION = "1.7.0 (Merge Fixed)"

# --- Database & Migration ---
def ensure_casting_schema_update():
    sql = "ALTER TABLE public.casting_applications ADD COLUMN IF NOT EXISTS media_message_ids jsonb;"
    try:
        # Это упрощенный вызов, в идеале делать через SQL редактор Supabase
        pass 
    except Exception as e:
        print(f"Migration error: {e}")

threading.Thread(target=ensure_casting_schema_update).start()

# --- Helpers ---

def optimize_url(url, width=800):
    if not url or "supabase.co" not in url: return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}width={width}&quality=80&format=origin"

def _normalize_url_list(value):
    if not value: return []
    if isinstance(value, list): return [v for v in value if isinstance(v, str) and v.startswith("http")]
    if isinstance(value, str):
        if value.startswith('['):
            try:
                data = json.loads(value)
                return [v for v in data if isinstance(v, str) and v.startswith("http")]
            except: pass
        return [v.strip() for v in value.split(',') if v.strip().startswith("http")]
    return []

def _tg_retry(fn, *args, **kwargs):
    for i in range(3):
        try:
            return fn(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 429:
                time.sleep(e.result_json.get('parameters', {}).get('retry_after', 1) + 1)
            else: raise
    return None

def format_casting_message(data, is_selected=False):
    def v(k): return str(data.get(k) or "—").replace("<", "&lt;").replace(">", "&gt;")
    header = "🟢 SELECTED: " if is_selected else ""
    return (
        f"{header}🌟 <b>АНКЕТА: {v('full_name')}</b>\n"
        f"🎯 Проект: <b>{v('casting_target')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Данные:</b> {v('city')} | {v('gender')} | {v('dob')}\n"
        f"📏 <b>Параметры:</b> {v('height_weight')} | {v('sizes')}\n"
        f"📱 <b>Inst:</b> {v('instagram')}\n"
        f"📞 <b>WhatsApp:</b> <code>{v('phone')}</code>\n\n"
        f"💡 <b>Опыт:</b> {v('experience')}\n"
        f"🎭 <b>Навыки:</b> {v('skills')}\n"
        f"💰 <b>Бюджет:</b> {v('fee_range')}\n"
    )

# --- Media Offloading ---

def offload_media_to_telegram(app_id, data):
    """Переносит фото из Supabase в TG канал для экономии места"""
    try:
        photos = _normalize_url_list(data.get('photo_urls'))
        video = data.get('video_audition_url')
        new_photos, new_video = [], video

        if photos:
            for url in photos:
                if 'supabase' in url:
                    msg = _tg_retry(bot.send_photo, MEDIA_CHANNEL_ID, optimize_url(url), disable_notification=True)
                    if msg: new_photos.append(f"tg://{msg.photo[-1].file_id}")
                else: new_photos.append(url)
        
        if video and 'supabase' in video:
            msg = _tg_retry(bot.send_video, MEDIA_CHANNEL_ID, video, disable_notification=True)
            if msg: new_video = f"tg://{msg.video.file_id}"

        update_payload = {
            "photo_urls": ",".join(new_photos) if new_photos else None,
            "video_audition_url": new_video
        }
        supabase.table('casting_applications').update(update_payload).eq('id', app_id).execute()
        data.update(update_payload)
    except Exception as e:
        print(f"Offload error: {e}")
    return data

# --- Docx Generation ---

def generate_casting_docx(applications, project_name):
    doc = Document()
    head = doc.add_heading(f'КАСТИНГ-ЛИСТ: {project_name}', 0)
    head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    table = doc.add_table(rows=0, cols=2)
    table.style = 'Table Grid'
    
    for app_data in applications:
        row = table.add_row()
        # Инфо
        c_info = row.cells[0]
        c_info.width = Cm(10)
        p = c_info.paragraphs[0]
        run = p.add_run(app_data.get('full_name', 'Без имени'))
        run.bold = True
        c_info.add_paragraph(f"Город: {app_data.get('city', '—')}\nВозраст: {app_data.get('dob', '—')}\nПараметры: {app_data.get('height_weight', '—')}")
        c_info.add_paragraph(f"тел: {app_data.get('phone', '—')}\nInst: {app_data.get('instagram', '—')}")

        # Фото
        c_pic = row.cells[1]
        c_pic.width = Cm(6)
        photos = _normalize_url_list(app_data.get('photo_urls'))
        if photos:
            try:
                # Берем первое фото для документа
                img_url = photos[0]
                if img_url.startswith('tg://'):
                    file_info = bot.get_file(img_url.replace('tg://', ''))
                    img_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
                
                resp = requests.get(optimize_url(img_url, width=400), timeout=5)
                if resp.status_code == 200:
                    img_stream = io.BytesIO(resp.content)
                    c_pic.paragraphs[0].add_run().add_picture(img_stream, width=Cm(5.5))
            except:
                c_pic.paragraphs[0].add_run("[Ошибка фото]")
    
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# --- Webhook Routes ---

@app.route('/api/casting', methods=['POST', 'OPTIONS'])
def notify_casting():
    if request.method == 'OPTIONS': return cors_response()
    try:
        data = request.json or {}
        cid = int(data.get('chat_id', 0))
        tid = int(data.get('thread_id', 0)) if data.get('thread_id') else None
        app_id = data.get('id') or data.get('application_id')
        
        if not cid: return jsonify({'error': 'no chat_id'}), 400

        # 1. Оффлоад
        data = offload_media_to_telegram(app_id, data)

        # 2. Формирование сообщения
        text = format_casting_message(data)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ВЫБРАТЬ", callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
        )

        # 3. Отправка (сначала альбом, потом текст с кнопками)
        photos = _normalize_url_list(data.get('photo_urls'))
        media = []
        for i, p_url in enumerate(photos[:3]): # Лимит 3 фото для компактности
            url = p_url.replace('tg://', '') if p_url.startswith('tg://') else p_url
            if i == 0:
                media.append(types.InputMediaPhoto(url, caption=f"📸 {data.get('full_name')}"))
            else:
                media.append(types.InputMediaPhoto(url))

        media_ids = []
        if media:
            sent_group = _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
            if sent_group: media_ids = [m.message_id for m in sent_group]

        sent_msg = _tg_retry(bot.send_message, cid, text, message_thread_id=tid, reply_markup=markup, parse_mode="HTML")
        
        if sent_msg:
            supabase.table("casting_applications").update({
                "tg_message_id": sent_msg.message_id,
                "media_message_ids": media_ids
            }).eq("id", app_id).execute()

        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Casting notify error: {e}")
        return jsonify({'error': str(e)}), 500

def cors_response():
    r = app.make_response('')
    r.headers.add('Access-Control-Allow-Origin', '*')
    r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    r.headers.add('Access-Control-Allow-Methods', 'POST')
    return r

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    cid, tid = message.chat.id, message.message_thread_id
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📅 КАЛЕНДАРЬ", url=f"{APP_URL}index.html?cid={cid}&tid={tid or ''}"),
        types.InlineKeyboardButton("🎭 КАСТИНГ", url=f"{APP_URL}casting.html?cid={cid}&tid={tid or ''}")
    )
    bot.send_message(cid, f"🦾 <b>GULYWOOD ERP v{VERSION}</b>", reply_markup=markup, message_thread_id=tid, parse_mode="HTML")

@bot.message_handler(commands=['reload'])
def handle_reload(message):
    cid, tid = message.chat.id, message.message_thread_id
    if not tid: return bot.reply_to(message, "Только в топиках!")
    
    status = bot.reply_to(message, "⏳ Загружаю анкеты проекта...")
    try:
        res = supabase.table("casting_applications").select("*").eq("thread_id", tid).order("created_at").execute()
        apps = res.data or []
        if not apps:
            bot.edit_message_text("Анкет пока нет.", cid, status.message_id)
            return

        bot.edit_message_text(f"Найдено {len(apps)} анкет. Начинаю вывод...", cid, status.message_id)
        
        for app_data in apps[:20]: # Ограничение для безопасности
            # Эмуляция входящего уведомления
            requests.post(f"{BASE_API_URL}/api/casting", json={**app_data, "chat_id": cid, "thread_id": tid})
            time.sleep(1)
            
        bot.delete_message(cid, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Ошибка: {e}", cid, status.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_sel:'))
def handle_select(call):
    app_id = call.data.split(':')[1]
    res = supabase.table("casting_applications").select("*").eq("id", app_id).execute()
    if res.data:
        new_status = not res.data[0].get('is_selected', False)
        supabase.table("casting_applications").update({"is_selected": new_status}).eq("id", app_id).execute()
        
        # Обновляем текст кнопки
        markup = call.message.reply_markup
        for row in markup.keyboard:
            for btn in row:
                if btn.callback_data == call.data:
                    btn.text = "✅ ВЫБРАН" if new_status else "ВЫБРАТЬ"
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "Статус обновлен")

@bot.message_handler(commands=['doc'])
def handle_doc(message):
    cid, tid = message.chat.id, message.message_thread_id
    if not tid: return
    
    status = bot.reply_to(message, "⏳ Собираю выбранных актеров...")
    res = supabase.table("casting_applications").select("*").eq("thread_id", tid).eq("is_selected", True).execute()
    
    if not res.data:
        bot.edit_message_text("Нет выбранных (зеленых) анкет.", cid, status.message_id)
        return
        
    doc_io = generate_casting_docx(res.data, "Project")
    doc_io.name = f"Casting_{tid}.docx"
    bot.send_document(cid, doc_io, message_thread_id=tid)
    bot.delete_message(cid, status.message_id)

# --- Webhook Setup ---
@app.route('/api', methods=['POST'])
def tg_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))