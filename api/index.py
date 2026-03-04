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
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

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
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Version indicator for debugging
VERSION = "1.7.1 (Backported & Merged)"

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def format_casting_message(data, is_selected=False):
    """
    Generates the HTML message body for a casting application.
    Reuse this in notify_casting and handle_app_select_callback to preserve formatting.
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
        
    if data.get('video_url'):
        full_txt += f"🎥 <a href='{data.get('video_url')}'>Видеовизитка</a>\n"
        
    # Get photos (handle string or list)
    photos = data.get('photo_urls', [])
    if isinstance(photos, str):
        import json
        try: photos = json.loads(photos)
        except: photos = []
        
    # If there are more than 3 photos, add links to the rest
    if isinstance(photos, list) and len(photos) > 3:
        full_txt += "\n🖼 <b>Дополнительные фото:</b>\n"
        for i, url in enumerate(photos[3:], 1):
            full_txt += f"• <a href='{url}'>Фото {i+3}</a>\n"
            
    return full_txt# --- Database & Migration ---
def ensure_casting_schema_update():
    sql = "ALTER TABLE public.casting_applications ADD COLUMN IF NOT EXISTS media_message_ids jsonb;"
    try:
        # Это упрощенный вызов, в идеале делать через SQL редактор Supabase
        pass 
    except Exception as e:
        print(f"Migration error: {e}")

threading.Thread(target=ensure_casting_schema_update).start()
# --- MEDIA OFFLOADING (CAMPOT2 Logic) ---

def optimize_url(url, width=800):
    if not url or "supabase.co" not in url: return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}width={width}&quality=80&format=origin"

# --- Helpers ---

def optimize_url(url, width=1280):
    """
    If URL is from Supabase Storage, append transformation params.
    """
    if not url: return url
    try:
        if "supabase.co" in url and "storage/v1/object/public" in url:
            # Check for image extensions
            ext = url.lower().split('.')[-1]
            if ext in ['jpg', 'jpeg', 'png', 'webp', 'tiff']:
                if '?' in url:
                    return f"{url}&width={width}&quality=80&format=origin"
                else:
                    return f"{url}?width={width}&quality=80&format=origin"
    except: pass
    return url

def _normalize_url_list(value):
    if not value: return []
    if isinstance(value, list): return [v for v in value if isinstance(v, str) and (v.startswith("http") or v.startswith("tg://"))]
    if isinstance(value, str):
        if value.strip().startswith('['):
            try:
                data = json.loads(value)
                return [v for v in data if isinstance(v, str) and (v.startswith("http") or v.startswith("tg://"))]
            except: pass
        return [v.strip() for v in value.split(',') if v.strip().startswith("http") or v.strip().startswith("tg://")]
    return []

def _tg_retry(fn, *args, **kwargs):
    for i in range(3):
        try:
            return fn(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 429:
                time.sleep(e.result_json.get('parameters', {}).get('retry_after', 1) + 1)
            else: raise
        except Exception as e:
            print(f"⚠️ TG Retry Attempt {i+1} Failed: {e}")
            if i == 2: raise
            time.sleep(1)
    return None


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

        # Photos (Visual Optimized)
        c_pic = row.cells[1]
        c_pic.width = Cm(6)
        photos_all = _normalize_url_list(app_data.get('photo_urls'))
        if photos_all:
            try:
                img_url = photos_all[0]
                if img_url.startswith('tg://'):
                    file_info = bot.get_file(img_url.replace('tg://', ''))
                    img_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
                
                resp = requests.get(optimize_url(img_url, width=400), timeout=10)
                if resp.status_code == 200:
                    img_stream = io.BytesIO(resp.content)
                    with Image.open(img_stream) as img:
                        img.thumbnail((600, 800))
                        opt_stream = io.BytesIO()
                        img.save(opt_stream, format="JPEG", quality=70)
                        opt_stream.seek(0)
                        c_pic.paragraphs[0].add_run().add_picture(opt_stream, width=Cm(5.5))
            except Exception as e:
                c_pic.paragraphs[0].add_run(f"[Ошибка фото: {e}]")
        else:
            p_p = c_pic.paragraphs[0]
            p_p.add_run("[Нет фото]").italic = True
            p_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Save to buffer
    f_out = io.BytesIO()
    doc.save(f_out)
    f_out.seek(0)
    return f_out

def fetch_casting_applications(chat_id, thread_id=None, page_size=500):
    all_rows = []
    offset = 0
    while True:
        q = supabase.table("casting_applications").select("*").eq("chat_id", chat_id)
        if thread_id is not None:
            q = q.eq("thread_id", thread_id)
        q = q.order("created_at", desc=False).range(offset, offset + page_size - 1)
        res = q.execute()
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows

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
        # Reset webhook and declare we want to drop pending updates
        new_url = APP_URL.replace("campotkz.github.io/media/", "media-seven-eta.vercel.app/api")
        bot.remove_webhook()
        bot.set_webhook(url=new_url, drop_pending_updates=True)
        return jsonify({"status": "ok", "message": "Pending updates dropped, webhook reset."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/report', methods=['POST', 'OPTIONS'])
def submit_report():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
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
        r = jsonify({'status': 'ok'})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r
    except Exception as e:
        r = jsonify({'error': str(e)}); r.headers.add('Access-Control-Allow-Origin', '*'); return r, 500

@app.route('/api/send_excel', methods=['POST', 'OPTIONS'])
def send_excel():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        data = request.json or {}
        project_name = data.get('project_name')
        filename = data.get('filename', 'Shoot_Export.xlsx')
        base64_data = data.get('base64_data')

        if not project_name or not base64_data:
            return jsonify({'error': 'Missing project_name or base64_data'}), 400

        # Find target chat/thread from database
        res = supabase.from_("clients").select("chat_id, thread_id").eq("name", project_name).execute()
        if not res.data:
            return jsonify({'error': f'Project "{project_name}" not found in database'}), 404
        
        target = res.data[0]
        chat_id = target.get('chat_id')
        thread_id = target.get('thread_id')

        if not chat_id:
            return jsonify({'error': f'Project "{project_name}" has no linked chat_id'}), 400

        # Decode base64 file
        file_bytes = base64.b64decode(base64_data)
        file_io = io.BytesIO(file_bytes)
        file_io.name = filename

        # Send to Telegram
        bot.send_document(chat_id, file_io, message_thread_id=thread_id)

        r = jsonify({'status': 'ok', 'message': f'File sent to {project_name}'})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r
    except Exception as e:
        r = jsonify({'error': str(e)})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r, 500

@bot.message_handler(commands=['start'])
def handle_start(message):
    cid = message.chat.id
    tid = message.message_thread_id or ''
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if tid:
        try:
            # Reactivate chat operations if it was stopped by /stop
            supabase.from_("clients").update({"is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
        except: pass

    # 1. Calendar
    cal_url = f"{APP_URL}index.html?cid={cid}&tid={tid}"
    markup.add(types.InlineKeyboardButton(text="📅 КАЛЕНДАРЬ", url=cal_url))
    
    # 2. Feedback
    fb_url = f"{APP_URL}feedback.html?cid={cid}&tid={tid}"
    markup.add(types.InlineKeyboardButton(text="📊 ФИДБЕК", url=fb_url))
    
    # 3. General Casting
    cast_url = f"{APP_URL}casting.html"
    markup.add(types.InlineKeyboardButton(text="🎭 КАСТИНГ", url=cast_url))
    
    # 4. Specific Casting (Only if in a topic)
    if tid:
        try:
            res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
            if res.data:
                pname = res.data[0]['name']
                import urllib.parse
                safe_pname = urllib.parse.quote(pname)
                spec_url = f"{APP_URL}casting.html?cid={cid}&tid={tid}&proj={safe_pname}&lock=1"
                markup.add(types.InlineKeyboardButton(text="🎯 ТОЛЬКО ЭТОТ КАСТИНГ", url=spec_url))
        except: pass

    bot.send_message(cid, "🦾 **GULYWOOD ERP**", reply_markup=markup, message_thread_id=tid or None, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if tid:
            # Mark client/topic as inactive to pause big loops (like /reload)
            supabase.from_("clients").update({"is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
            bot.reply_to(message, "🛑 **БОТ ОСТАНОВЛЕН**\nВсе цикличные действия (включая загрузку анкет) в этом топике прерваны.\n\nНажмите /start чтобы снова активировать бота для этого топика.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ Вы можете останавливать бота только внутри топика проекта.")
    except Exception as e:
        print(f"Stop Error: {e}")

@bot.message_handler(commands=['cal'])
def handle_calendar(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id or ''
        markup = types.InlineKeyboardMarkup()
        cal_url = f"{APP_URL}index.html?cid={cid}&tid={tid}"
        markup.add(types.InlineKeyboardButton(text="📅 ОТКРЫТЬ КАЛЕНДАРЬ", url=cal_url))
        bot.send_message(cid, "🗓 **GULYWOOD CALENDAR**", reply_markup=markup, message_thread_id=tid or None, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['status'])
def handle_status(message):
    try:
        user = message.from_user
        res = supabase.from_("team").select("*").eq("telegram_id", user.id).execute()
        pos = res.data[0].get('position') if res.data else "не зарегистрирован"
        bot.reply_to(message, f"🤖 **Bot Status**\nVersion: `{VERSION}`\nUser: `{user.first_name}`\nID: `{user.id}`\nPosition: `{pos}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Status Error: {e}")

@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    cid, tid = message.chat.id, message.message_thread_id or ""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📊 ЗАПОЛНИТЬ МЕТРИКИ", url=f"{APP_URL}feedback.html?cid={cid}&tid={tid}"))
    bot.send_message(cid, f"📉 **СВЕРКА МЕТРИК**\n\n`{APP_URL}feedback.html?cid={cid}&tid={tid}`", reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Goldy | Luxury`", parse_mode="Markdown")
            return
        
        # Determine category from chat title (group name)
        chat_title = message.chat.title or ""
        category = 'casting' if 'КАСТИНГ' in chat_title.upper() else 'media'
        
        # 1. Update existing
        res = supabase.from_("clients").update({"name": new_name, "category": category}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. If no rows updated, create it with the correct name and category
        if not res.data:
            ensure_project(cid, tid, chat_title, forced_name=new_name)
            bot.reply_to(message, f"✅ Проект создан и назван: **{new_name}**")
        else:
            bot.reply_to(message, f"✅ Проект переименован: **{new_name}**")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}")

@bot.message_handler(commands=['on'])
def handle_on_command(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        chat_title = message.chat.title or "Unknown"
        
        # 1. Ensure project exists
        ensure_project(cid, tid, chat_title)
        
        # 2. Set Active (Visible in Calendar)
        # We KEEP is_hidden=True if it was already hidden.
        # This allows user to work in Calendar without exposing project to public form.
        
        # However, we must ensure we don't accidentally UNHIDE it if user wanted it hidden.
        # But wait, if project was closed (is_active=False, is_hidden=True), and we run /on:
        # We want is_active=True, is_hidden=True.
        
        # Let's just update is_active.
        res = supabase.from_("clients").update({"is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        bot.reply_to(message, 
            "✅ **ПРОЕКТ АКТИВИРОВАН В КАЛЕНДАРЕ**\n"
            "Теперь он доступен для выбора в ERP (даже если топик закрыт).\n"
            "Публичная видимость в анкете не изменена.",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['archive'])
def handle_archive(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return
        
        # 1. Try exact match
        res = supabase.from_("clients").update({"is_hidden": True, "is_active": False}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. Try match by tid where chat_id is null (legacy cleanup)
        if not res.data:
            res = supabase.from_("clients").update({"is_hidden": True, "is_active": False, "chat_id": cid}).is_("chat_id", "null").eq("thread_id", tid).execute()
        
        if res.data:
            bot.reply_to(message, "🗄️ **АРХИВИРОВАНО**\nЭтот топик скрыт из всех списков выбора на сайте.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден в базе данных. Попробуйте сначала создать ссылку командой `/cast_link` или просто подождать.", parse_mode="Markdown")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка архивации: {e}")

@bot.message_handler(commands=['unarchive'])
def handle_unarchive(message):
    try:
        cid, tid = message.chat.id, message.message_thread_id
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return
            
        # 1. Try exact match
        res = supabase.from_("clients").update({"is_hidden": False, "is_active": True}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. Try match by tid where chat_id is null
        if not res.data:
            res = supabase.from_("clients").update({"is_hidden": False, "is_active": True, "chat_id": cid}).is_("chat_id", "null").eq("thread_id", tid).execute()

        if res.data:
            bot.reply_to(message, "🔓 **РАЗАРХИВИРОВАНО**\nТопик снова доступен в списках выбора.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден.", parse_mode="Markdown")
    except Exception as e: bot.reply_to(message, f"❌ Ошибка разархивации: {e}")

@bot.message_handler(commands=['casting'])
def handle_general_casting(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        link = f"{APP_URL}casting.html"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎭 ОТКРЫТЬ ОБЩИЙ КАСТИНГ", url=link))
        
        msg = (
            f"🌟 <b>УНИВЕРСАЛЬНАЯ ССЫЛКА НА КАСТИНГ</b>\n\n"
            f"Эта ссылка позволяет кандидату выбрать любой активный проект.\n"
            f"🔗 <code>{link}</code>"
        )
        m = bot.send_message(cid, msg, reply_markup=markup, message_thread_id=tid, parse_mode="HTML")
        auto_delete(m, delay=60)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка генерации ссылки: {e}")

@bot.message_handler(commands=['cast_link'])
def handle_specific_casting(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return

        # Ensure project exists
        ensure_project(cid, tid, message.chat.title)
        
        # Get project name
        res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
        if not res.data:
            bot.reply_to(message, "❌ Проект не найден.")
            return
            
        pname = res.data[0]['name']
        import urllib.parse
        safe_pname = urllib.parse.quote(pname)
        
        link = f"{APP_URL}casting.html?cid={cid}&tid={tid}&proj={safe_pname}&lock=1"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="🎯 ЗАПОЛНИТЬ АНКЕТУ (ТОЛЬКО ЭТОТ)", url=link))
        
        msg = (
            f"🎯 <b>КАСТИНГ: {pname}</b>\n\n"
            f"Ссылка только для этого проекта (другие скрыты).\n"
            f"🔗 <code>{link}</code>"
        )
        bot.send_message(cid, msg, reply_markup=markup, message_thread_id=tid, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['timer'])
def handle_timer(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return

        # 1. Ensure project exists
        ensure_project(cid, tid, message.chat.title)
        
        # 2. Get project details for the link
        p_res = supabase.from_("clients").select("id, name").eq("chat_id", cid).eq("thread_id", tid).execute()
        
        if p_res.data:
            p = p_res.data[0]
            pid = p['id']
            pname = p['name']
            
            # 3. Create TWA Keyboard
            url = f"{APP_URL}timer.html?pid={pid}&proj={pname.replace(' ', '%20')}&tid={tid or ''}&cid={cid}"
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton(text="⏱️ ЗАПУСТИТЬ ТАЙМЕР", url=url)
            markup.add(btn)
            
            bot.send_message(cid, f"🚀 **FILM TIMER PRO**\n\nПроект: **{pname}**\n\nНажмите кнопку ниже, чтобы начать замер смены.", 
                             reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден. Попробуйте написать что-нибудь в этот топик сначала.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка таймера: {e}")

@bot.message_handler(commands=['loc'])
def handle_project_location(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id if getattr(message, 'is_topic_message', False) else None
        
        if not tid:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика.")
            return

        loc_name = (message.text or "").replace('/loc', '').strip()
        if not loc_name:
            bot.reply_to(message, "📝 Напишите название локации после команды. Пример: `/loc Магазин очков №1`", parse_mode="Markdown")
            return

        # 1. Ensure project exists and get its ID
        ensure_project(cid, tid, message.chat.title)
        p_res = supabase.from_("clients").select("id, name").eq("chat_id", cid).eq("thread_id", tid).execute()
        
        if p_res.data:
            pid = p_res.data[0]['id']
            pname = p_res.data[0]['name']
            
            # 2. Upsert location
            supabase.table("project_locations").upsert({
                "project_id": pid, "name": loc_name
            }, on_conflict="project_id, name").execute()
            
            bot.reply_to(message, f"📍 Локация **{loc_name}** сохранена для проекта **{pname}**.\nТеперь она будет доступна в подсказках на сайте.")
        else:
            bot.reply_to(message, "❌ Ошибка: Проект не найден.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка добавления локации: {e}")

@bot.message_handler(commands=['add'])
def handle_add(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👥 Актер", callback_data=f"add_cat:actors:{tid}"),
            types.InlineKeyboardButton("🛠 Сотрудник", callback_data=f"add_cat:crew:{tid}"),
            types.InlineKeyboardButton("🤝 Клиент", callback_data=f"add_cat:clients:{tid}"),
            types.InlineKeyboardButton("📍 Локация", callback_data=f"add_cat:locs:{tid}"),
            types.InlineKeyboardButton("🔗 Ссылка", callback_data=f"add_cat:links:{tid}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="add_cancel")
        )
        bot.send_message(cid, "➕ **ДОБАВЛЕНИЕ ДАННЫХ**\nЧто вы хотите добавить в этот проект?", 
                         reply_markup=markup, message_thread_id=tid, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка добавления: {e}")

@bot.message_handler(commands=['rename'])
def handle_rename(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Проект А` (Бот должен быть админом)", parse_mode="Markdown")
            return

        # Attempt to rename topic
        bot.edit_forum_topic(cid, tid, name=new_name)
        
        # Also update in DB
        supabase.table("clients").update({"name": new_name}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        bot.reply_to(message, f"✅ Топик переименован в **{new_name}** и обновлен в базе.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка переименования: {e}\n(Проверьте, является ли бот администратором с правом управления темами)")

@bot.message_handler(commands=['del'])
def handle_delete(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        # 1. CONTEXTUAL MODE (Reply)
        if message.reply_to_message:
            reply = message.reply_to_message
            txt = (reply.text or reply.caption or "")
            
            # 1.1 Check for Links
            urls = re.findall(r'(https?://[^\s]+)', txt)
            if urls:
                deleted_urls = []
                for url in urls:
                    res = supabase.table("project_resources").delete().eq("chat_id", cid).eq("thread_id", tid).eq("url", url).execute()
                    if res.data: deleted_urls.append(url)
                
                if deleted_urls:
                    bot.reply_to(message, f"✅ Удалено из базы: {len(deleted_urls)} ссылок")
                else:
                    bot.reply_to(message, "ℹ️ Ссылки не найдены в базе проекта.")
    except Exception as e:
        print(f"Delete Error: {e}")
    return False

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

        # --- 0. BLACKLIST CHECK ---
        try:
            if phone or insta:
                bl_query = supabase.table("blacklist").select("id")
                if phone and insta:
                    bl_query = bl_query.or_(f"phone.eq.{phone},instagram.eq.{insta}")
                elif phone:
                    bl_query = bl_query.eq("phone", phone)
                elif insta:
                    bl_query = bl_query.eq("instagram", insta)
                
                bl_res = bl_query.execute()
                if bl_res.data:
                    print(f"🚫 BLOCKED: Application from {phone}/{insta} is in Blacklist.")
                    return jsonify({'status': 'blocked', 'message': 'User is blacklisted'}), 200
        except Exception as bl_err:
            print(f"⚠️ Blacklist Check Failed: {bl_err}")
            # Try to auto-fix the DB if table is missing
            if "relation \"public.blacklist\" does not exist" in str(bl_err) or "404" in str(bl_err):
                ensure_blacklist_table()

        # Cast to integers
        try:
            cid = int(cid)
            tid = int(tid) if tid and str(tid).isdigit() and int(tid) > 0 else None
            print(f"✅ Parsed Target: CID={cid}, TID={tid}")
        except ValueError:
            print(f"❌ Invalid CID/TID: {cid} / {tid}")
            return jsonify({'error': 'Invalid chat_id or thread_id format'}), 400

        print(f"DEBUG: notify_casting for project: {target} (phone: {phone}, insta: {insta})")

        # --- NEW: STRICT MEDIA OFFLOADING ---
        app_id_for_offload = data.get('application_id') or data.get('id')
        if app_id_for_offload:
            data = offload_media_to_telegram(app_id_for_offload, data)

        # 0. SELF-CLEANUP: If this is an UPDATE to an existing application, 
        # delete its previous message FIRST.
        app_id = data.get('application_id')
        if app_id:
            try:
                # Fetch the CURRENT record to see if it has an old message ID
                self_res = supabase.table("casting_applications").select("tg_message_id, photo_urls, video_audition_url").eq("id", app_id).single().execute()
                if self_res.data:
                    old_msg_id = self_res.data.get('tg_message_id')
                    
                    if old_msg_id:
                        print(f"🔄 Self-Cleanup: Deleting old message {old_msg_id} for app {app_id}")
                        try:
                            # Delete main text message
                            bot.delete_message(cid, old_msg_id)
                            
                            # Delete associated media
                            media_count = 0
                            old_photos = self_res.data.get('photo_urls') or []
                            old_video = self_res.data.get('video_audition_url')
                            media_count = len(old_photos)
                            if old_video: media_count += 1
                            media_count = min(media_count, 10) # Safety
                            
                            for i in range(1, media_count + 1):
                                try: bot.delete_message(cid, int(old_msg_id) - i)
                                except: pass
                        except Exception as e:
                            print(f"⚠️ Self-Cleanup Failed (msg too old?): {e}")
            except Exception as e:
                print(f"⚠️ Self-Cleanup Error: {e}")

        # 1. FIND AND DELETE DUPLICATES (Strictly Different IDs)
        try:
            # Search by phone OR instagram for the same project
            # AND exclude the current application (app_id) we just created
            query = supabase.table("casting_applications").select("id, tg_message_id, photo_urls, video_audition_url")
            
            # Match by project (target) AND chat context (cid/tid) to be safer
            # We want to delete ONLY duplicates in THIS specific chat/topic
            query = query.eq("chat_id", cid)
            if tid:
                query = query.eq("thread_id", tid)
            
            # Match by phone or instagram
            conditions = []
            if phone and len(str(phone)) > 5:
                conditions.append(f"phone.eq.{phone}")
            if insta and len(str(insta)) > 2:
                conditions.append(f"instagram.eq.{insta}")
            
            if conditions:
                query = query.or_(",".join(conditions))
            else:
                # Fallback: if no phone/insta, maybe search by name? No, too risky.
                # Just skip dedup if no identifiers.
                print("⚠️ Deduplication skipped: No valid phone or instagram to match.")
                raise Exception("No identifiers for deduplication")
            
            # CRITICAL: Exclude the CURRENT application ID (if we have it)
            # Otherwise we might delete the record we just inserted if logic is flawed
            app_id = data.get('application_id') or data.get('id')
            if app_id:
                query = query.neq("id", app_id)

            # Get OLD records that have a telegram message ID
            old_res = query.not_.is_("tg_message_id", "null").order("created_at", descending=True).execute()
            
            if old_res.data:
                for old_app in old_res.data:
                    old_msg_id = old_app.get('tg_message_id')
                    old_db_id = old_app.get('id')
                    
                    print(f"🗑️ Found duplicate: {old_db_id} (msg: {old_msg_id})")

                    # 1.1 Delete from Telegram
                    if old_msg_id:
                        try:
                            # Try to delete the main text message
                            bot.delete_message(cid, old_msg_id)
                            print(f"   Deleted text msg {old_msg_id}")
                            
                            # SMART MEDIA DELETION:
                            media_count = 0
                            try:
                                old_photos = old_app.get('photo_urls') or []
                                old_video = old_app.get('video_audition_url')
                                
                                media_count = len(old_photos)
                                if old_video: media_count += 1
                                
                                # Safety limit: don't delete more than 10 messages blindly
                                media_count = min(media_count, 10)
                            except: 
                                media_count = 3 # Fallback default
                                
                            print(f"   Attempting to delete {media_count} media messages for app {old_db_id}")

                            # The text message (old_msg_id) was sent LAST.
                            for i in range(1, media_count + 1):
                                try: 
                                    target_id = int(old_msg_id) - i
                                    bot.delete_message(cid, target_id)
                                    print(f"   Deleted media msg {target_id}")
                                except Exception as e:
                                    print(f"   Failed to delete media {target_id}: {e}")
                                    pass
                        except Exception as tg_del_e: 
                            print(f"   TG Delete Err: {tg_del_e}")
                    
                    # 1.2 Delete from Supabase
                    # Only delete duplicates (different IDs), never the current one (self-cleanup handles msg deletion only)
                    supabase.table("casting_applications").delete().eq("id", old_db_id).execute()
                    print(f"✅ Deduplicated: Deleted old application {old_db_id}")
        except Exception as dedup_e:
            print(f"Deduplication Error: {dedup_e}")

        # 2. Auto-Register Contact
        try:
            name, phone = data.get('full_name'), data.get('phone')
            if name and phone:
                supabase.table("contacts").upsert({
                    "name": name, "phone": phone, "thread_id": tid, "chat_id": cid, "category": "casting"
                }, on_conflict="phone,chat_id,thread_id").execute()
        except: pass

        # 2. Format Message (HTML for better reliability)
        def v(k): return str(data.get(k) or "—").replace("<", "&lt;").replace(">", "&gt;")
        
        # IMPROVED LAYOUT (Using Helper)
        full_txt = format_casting_message(data)

        # USE A SIMPLE SAFE CAPTION FOR MEDIA GROUP to avoid 1024 limit and HTML breakage
        simple_caption = (
            f"📸 <b>Анкета: {v('full_name')}</b>\n"
            f"🎯 {v('casting_target')}\n\n"
            f"Описание придет следующим сообщением... ⬇️"
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
        print(f"Casting Notify Error: {e}")
        r = jsonify({'error': str(e)}); r.headers.add('Access-Control-Allow-Origin', '*'); return r, 500

@bot.message_handler(commands=['del'])
def handle_del_app_command(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой для удаления.")
            return

        # 1. FIND THE APPLICATION DATA
        target_reply = reply
        if "АНКЕТА:" not in (reply.text or reply.caption or ""):
            if reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or ""):
                target_reply = reply.reply_to_message
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ.")
                return

        res = supabase.table("casting_applications").select("id").eq("tg_message_id", target_reply.message_id).execute()
        if not res.data:
            bot.reply_to(message, "❌ Анкета не найдена в базе.")
            return
        
        app_id = res.data[0]['id']
        
        # Cleanup command
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
        
        # Reuse callback logic
        handle_app_delete_callback(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", 
                                                      message=target_reply, data=f"app_del:{app_id}"))

    except Exception as e:
        print(f"Manual Del Error: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.forward_from_chat or m.forward_from)
def handle_forwarded_message(message):
    try:
        # Check if this is an application message being forwarded
        txt = message.text or message.caption or ""
        if "АНКЕТА:" not in txt:
            return

        cid, tid = message.chat.id, message.message_thread_id
        if not tid: return # Only handle topics

        # Extract name and phone/insta from text to find original record
        m_name = re.search(r'АНКЕТА:\s*([^\n<]+)', txt, re.IGNORECASE)
        m_phone = re.search(r'📞\s*([^\n<]+)', txt)
        m_insta = re.search(r'📱\s*Instagram:\s*([^\n<]+)', txt)

        found_name = m_name.group(1).strip().replace("<b>", "").replace("</b>", "") if m_name else None
        phone = m_phone.group(1).strip() if m_phone else None
        insta = m_insta.group(1).strip() if m_insta else None

        if not (phone or insta): return

        # 1. Ensure project (topic) exists in DB
        ensure_project(cid, tid, message.chat.title)
        p_res = supabase.from_("clients").select("name").eq("chat_id", cid).eq("thread_id", tid).execute()
        new_project_name = p_res.data[0]['name'] if p_res.data else "Unknown"

        # 2. Update/Insert contact for THIS topic
        if phone:
            supabase.table("contacts").upsert({
                "name": found_name or "Unknown",
                "phone": phone,
                "chat_id": cid,
                "thread_id": tid,
                "category": "casting"
            }, on_conflict="phone,chat_id,thread_id").execute()

        # 3. Create a NEW entry in casting_applications for this project
        # Search for the most recent application by this actor to copy photos/video
        query = supabase.table("casting_applications").select("*")
        if phone: query = query.eq("phone", phone)
        elif insta: query = query.eq("instagram", insta)
        
        orig_res = query.order("created_at", descending=True).limit(1).execute()
        
        if orig_res.data:
            orig = orig_res.data[0]
            # Create NEW record for the NEW project
            new_app = {
                **orig,
                "casting_target": new_project_name,
                "project_name": new_project_name,
                "chat_id": cid,
                "thread_id": tid,
                "tg_message_id": message.message_id # Link to the forwarded message
            }
            # Remove keys that shouldn't be duplicated exactly or will be auto-generated
            new_app.pop('id', None)
            new_app.pop('created_at', None)
            
            supabase.table("casting_applications").insert([new_app]).execute()
            
            # 4. Add the Delete button to the forwarded message by sending a small "control" message
            markup = types.InlineKeyboardMarkup()
            # Find the ID of the newly created record
            fresh_res = supabase.table("casting_applications").select("id").eq("phone", phone).eq("casting_target", new_project_name).order("created_at", descending=True).limit(1).execute()
            if fresh_res.data:
                markup.add(types.InlineKeyboardButton("🗑️ УДАЛИТЬ ИЗ ЭТОГО ТОПИКА", callback_data=f"app_del:{fresh_res.data[0]['id']}"))
                conf_msg = bot.reply_to(message, f"✅ Актер **{found_name}** добавлен в проект **{new_project_name}**.", reply_markup=markup)
                
                # Auto-delete confirmation message after 10 seconds to keep chat clean
                import threading
                import time
                def delayed_delete(chat_id, msg_id):
                    time.sleep(10)
                    try: bot.delete_message(chat_id, msg_id)
                    except: pass
                
                threading.Thread(target=delayed_delete, args=(cid, conf_msg.message_id)).start()
            
            print(f"🔄 FORWARD SYNC: Actor {found_name} synced to new project {new_project_name}")

    except Exception as e:
        print(f"Forward Sync Err: {e}")

@bot.message_handler(commands=['foto', 'video'])
def handle_actor_update_link(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой актера.")
            return

        # Find the application in DB
        # 1. Try by Message ID
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", reply.message_id).execute()
        
        # 2. Try by Message ID of the reply target (if reply is to a media group item)
        if not res.data and reply.reply_to_message:
             res = supabase.table("casting_applications").select("*").eq("tg_message_id", reply.reply_to_message.message_id).execute()

        # 3. Try searching by NAME and PROJECT (Topic)
        if not res.data:
            txt = reply.text or reply.caption or ""
            # Extract Name from "🌟 НОВАЯ АНКЕТА: Имя Фамилия"
            m_name = re.search(r'АНКЕТА:\s*([^\n<]+)', txt, re.IGNORECASE)
            
            # Or from "📸 Анкета: Имя Фамилия" (Media caption)
            if not m_name:
                m_name = re.search(r'Анкета:\s*([^\n<]+)', txt, re.IGNORECASE)

            if m_name:
                found_name = m_name.group(1).strip().replace("<b>", "").replace("</b>", "")
                print(f"DEBUG: Searching by name '{found_name}' in chat {message.chat.id}")
                
                # Search by name AND current chat/thread to avoid duplicates
                query = supabase.table("casting_applications").select("*").ilike("full_name", f"%{found_name}%")
                
                # If we are in a topic, filter by thread_id
                if message.message_thread_id:
                     query = query.eq("thread_id", message.message_thread_id)
                
                res = query.order("created_at", descending=True).limit(1).execute()
        
            # 4. Try searching by PHONE or INSTAGRAM found in text
            if not res.data:
                # Phone pattern (digits, possibly with +)
                phone_match = re.search(r'(?:\+?\d[\d\-\s]{8,})', txt)
                # Instagram pattern (after "Inst:" or similar)
                insta_match = re.search(r'Inst:\s*([^\n\s]+)', txt, re.IGNORECASE)

                query = supabase.table("casting_applications").select("*")
                conditions = []

                if phone_match:
                    found_phone = re.sub(r'\D', '', phone_match.group(0)) # Clean non-digits
                    if len(found_phone) > 6:
                        # Use ILIKE for partial match or just simple match
                        print(f"DEBUG: Searching by phone '{found_phone}'")
                        conditions.append(f"phone.ilike.%{found_phone}%")

                if insta_match:
                    found_insta = insta_match.group(1).strip()
                    if len(found_insta) > 2:
                        print(f"DEBUG: Searching by insta '{found_insta}'")
                        conditions.append(f"instagram.eq.{found_insta}")

                if conditions:
                    query = query.or_(",".join(conditions))
                    # Filter by thread/topic to be safe
                    if message.message_thread_id:
                        query = query.eq("thread_id", message.message_thread_id)
                    
                    res = query.order("created_at", descending=True).limit(1).execute()

            # 5. Last Resort: Find LATEST application in this topic
            if not res.data and message.message_thread_id:
                print("DEBUG: Using Last Resort - fetching latest app in topic")
                res = supabase.table("casting_applications").select("*")\
                    .eq("chat_id", message.chat.id)\
                    .eq("thread_id", message.message_thread_id)\
                    .order("created_at", descending=True)\
                    .limit(1)\
                    .execute()

        if not res.data:
            bot.reply_to(message, "❌ Не удалось найти анкету. Попробуйте найти её по имени или телефону вручную.")
            return

        app_data = res.data[0]
        update_type = 'photo' if 'foto' in message.text else 'video'
        
        # Generate Personal Link with EXPLICIT Context
        # We pass cid/tid to ensure we know exactly where to return the result
        cid = message.chat.id
        tid = message.message_thread_id or 0
        
        # Safe project name from chat title or topic name could be added too, but IDs are most important
        link = f"https://campotkz.github.io/media/update.html?id={app_data['id']}&type={update_type}&cid={cid}&tid={tid}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=f"📥 ДОБАВИТЬ {'ФОТО' if update_type == 'photo' else 'ВИДЕО'}", url=link))
        
        type_text = "фотографии" if update_type == 'photo' else "видео-визитку"
        msg = (
            f"👤 **АКТЕР:** {app_data['full_name']}\n"
            f"📱 **ТЕЛЕФОН:** {app_data['phone']}\n\n"
            f"🔗 **ССЫЛКА ДЛЯ ЗАГРУЗКИ:**\n"
            f"`{link}`\n\n"
            f"Отправьте эту ссылку актеру. Когда он загрузит {type_text}, они автоматически добавятся сюда ответом на анкету."
        )
        
        # Send message with button and link
        m = bot.send_message(message.chat.id, msg, reply_markup=markup, message_thread_id=message.message_thread_id, parse_mode="Markdown")
        
        # Cleanup command message only
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass

    except Exception as e:
        print(f"Actor Update Link Err: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: (m.text and "/add" in m.text) or (m.caption and "/add" in m.caption), content_types=['text', 'photo', 'video', 'document'])
def handle_add_media_legacy(message):
    # Rename this handler to avoid conflict or just remove it if unused.
    # It seems to be conflicting with /foto and /video commands?
    pass
def handle_manual_add_media(message):
    try:
        reply = message.reply_to_message
        if not reply:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение с анкетой, чтобы добавить медиа.")
            return

        # 1. FIND THE APPLICATION DATA
        target_reply = reply
        # If the reply is NOT the bot's application, try to find it in the chain
        if "АНКЕТА:" not in (reply.text or reply.caption or ""):
            if reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or ""):
                target_reply = reply.reply_to_message
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ.")
                return

        # 2. Check if media is already in the command message
        source_msg = message
        is_direct_upload = source_msg.video or source_msg.photo
        
        if not is_direct_upload:
            # Interactive mode: Ask user to send media
            prompt = bot.reply_to(message, "📥 **ОЖИДАНИЕ МЕДИА**\nПришлите фото или видео **ОТВЕТОМ** на это сообщение для анкеты актера.", parse_mode="Markdown")
            return

        # Direct mode logic (media already in /add message)
        process_manual_media_update(message, target_reply)

    except Exception as e:
        print(f"Manual Update Error: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", message_thread_id=message.message_thread_id)

def process_manual_media_update(source_msg, application_msg):
    try:
        cid, tid = source_msg.chat.id, source_msg.message_thread_id
        
        # Search DB by application_msg.message_id
        res = supabase.table("casting_applications").select("*").eq("tg_message_id", application_msg.message_id).execute()
        if not res.data:
            bot.send_message(cid, "❌ Анкета не найдена в базе (возможно, она слишком старая).", message_thread_id=tid)
            return
        
        app_data = res.data[0]
        new_video = app_data.get('video_audition_url')
        new_photos = app_data.get('photo_urls') or []
        
        # 2. Extract Media (Video/Photo)
        is_updated = False
        if source_msg.video:
            bot.send_chat_action(cid, 'upload_video', message_thread_id=tid)
            f_info = bot.get_file(source_msg.video.file_id)
            f_bytes = bot.download_file(f_info.file_path)
            path = f"video/manual_{app_data['id']}_{int(datetime.now().timestamp())}.mp4"
            supabase.storage.from_('casting_media').upload(path, f_bytes)
            new_video = supabase.storage.from_('casting_media').get_public_url(path)
            is_updated = True
        elif source_msg.photo:
            bot.send_chat_action(cid, 'upload_photo', message_thread_id=tid)
            f_info = bot.get_file(source_msg.photo[-1].file_id)
            f_bytes = bot.download_file(f_info.file_path)
            path = f"photo/manual_{app_data['id']}_{int(datetime.now().timestamp())}.jpg"
            supabase.storage.from_('casting_media').upload(path, f_bytes)
            new_photos.append(supabase.storage.from_('casting_media').get_public_url(path))
            is_updated = True
            
        if not is_updated: return

        # 3. Update DB
        supabase.table("casting_applications").update({
            "photo_urls": new_photos,
            "video_audition_url": new_video
        }).eq("id", app_data['id']).execute()

        # 4. Trigger Repost
        updated_payload = {
            **app_data,
            "photo_urls": new_photos,
            "video_audition_url": new_video,
            "chat_id": cid,
            "thread_id": tid
        }

        # Delete OLD message
        try:
            bot.delete_message(cid, application_msg.message_id)
            try: bot.delete_message(cid, int(application_msg.message_id) - 1)
            except: pass
        except: pass

        # Delete command message and its parents if interactive
        try: bot.delete_message(cid, source_msg.message_id)
        except: pass
        if source_msg.reply_to_message and "ОЖИДАНИЕ МЕДИА" in (source_msg.reply_to_message.text or ""):
            try: 
                # Delete the "/add" command that triggered the prompt
                bot.delete_message(cid, source_msg.reply_to_message.reply_to_message.message_id)
                # Delete the bot prompt itself
                bot.delete_message(cid, source_msg.reply_to_message.message_id)
            except: pass

        # SEND NEW MESSAGE
        import requests
        requests.post('https://media-seven-eta.vercel.app/api/casting', json=updated_payload)

    except Exception as e:
        print(f"process_manual_media_update err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reload_batch:'))
def handle_reload_batch_callback(call):
    try:
        _, offset_str = call.data.split(':')
        offset = int(offset_str)
        cid, tid = call.message.chat.id, call.message.message_thread_id
        
        # Reuse logic by calling handle_reload_command with offset
        # But handle_reload_command expects a Message object. 
        # We can construct a fake message or refactor.
        # Better: Refactor the core logic into a separate function.
        
        bot.answer_callback_query(call.id, "Загружаю следующую партию...")
        threading.Thread(target=process_reload_batch, args=(cid, tid, offset, call.message)).start()
        
    except Exception as e:
        print(f"Reload Batch Err: {e}")

def process_reload_batch(cid, tid, offset=0, status_msg=None):
    try:
        BATCH_SIZE = 10
        
        # 1. Fetch ALL apps (cached or fresh)
        # Note: Fetching ALL every time is inefficient but safest for consistency.
        # Optimization: fetch_casting_applications could take offset/limit, 
        # but we need to DEDUPLICATE first, so we must fetch all (or enough) to dedupe correctly.
        # Given user has ~60 apps, fetching all is fine.
        
        all_apps = fetch_casting_applications(cid, tid)
        if not all_apps:
            if status_msg:
                _tg_retry(bot.edit_message_text, f"⚠️ Анкет не найдено.", cid, status_msg.message_id)
            return

        # 2. Deduplicate
        unique_map = {}
        to_delete = []
        for app in sorted(all_apps, key=lambda x: x.get('created_at')):
            phone = app.get('phone')
            key = phone if (phone and len(str(phone)) > 5) else (app.get('instagram') or app.get('id'))
            if key in unique_map:
                to_delete.append(unique_map[key]['id'])
            unique_map[key] = app
            
        # Cleanup DB duplicates
        if to_delete:
            print(f"🗑️ Deleting {len(to_delete)} duplicates from Supabase")
            for d_id in to_delete:
                supabase.table("casting_applications").delete().eq("id", d_id).execute()

        clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))
        total_count = len(clean_apps)
        
        # Slice Batch
        batch = clean_apps[offset : offset + BATCH_SIZE]
        
        if not batch:
            if status_msg:
                _tg_retry(bot.edit_message_text, f"✅ Все анкеты загружены ({total_count}). Удалено дублей: {len(to_delete)}", cid, status_msg.message_id)
            return

        # Notify Start of Batch
        if status_msg:
            _tg_retry(bot.edit_message_text, f"⏳ Загрузка {offset+1}-{min(offset+BATCH_SIZE, total_count)} из {total_count}...\n(Миграция медиа в Telegram)", cid, status_msg.message_id)
        
        # Send Batch
        for app_data in batch:
            try:
                # CHECK FOR STOP COMMAND EARLY
                if tid:
                    cl_check = supabase.from_("clients").select("is_active").eq("chat_id", cid).eq("thread_id", tid).execute()
                    if cl_check.data and cl_check.data[0].get("is_active") is False:
                        if status_msg:
                            try: bot.edit_message_text(f"🛑 Загрузка прервана командой /stop.", cid, status_msg.message_id)
                            except: pass
                        return 

                # MIGRATE MEDIA IF NEEDED (User Request)
                app_data = offload_media_to_telegram(app_data['id'], app_data)

                # CHECK FOR STOP COMMAND AGAIN (in case offload took a long time)
                if tid:
                    cl_check = supabase.from_("clients").select("is_active").eq("chat_id", cid).eq("thread_id", tid).execute()
                    if cl_check.data and cl_check.data[0].get("is_active") is False:
                        if status_msg:
                            try: bot.edit_message_text(f"🛑 Загрузка прервана командой /stop.", cid, status_msg.message_id)
                            except: pass
                        return 

                app_id = app_data.get('id')
                safe_app = dict(app_data)
                photos = _normalize_url_list(safe_app.get("photo_urls"))
                safe_app["photo_urls"] = photos

                # Prepare Media
                media = []
                for i, url in enumerate(photos[:3]):
                    opt_url = optimize_url(url, width=1024)
                    media.append(types.InputMediaPhoto(opt_url))

                full_txt = format_casting_message(safe_app, is_selected=safe_app.get('is_selected', False))

                markup = types.InlineKeyboardMarkup()
                sel_txt = "✅ ВЫБРАН" if safe_app.get('is_selected') else "ВЫБРАТЬ"
                markup.add(
                    types.InlineKeyboardButton(sel_txt, callback_data=f"app_sel:{app_id}"),
                    types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
                )

                sent_msg = None
                
                if media:
                    try:
                        _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
                    except Exception as e:
                        print(f"Reload Media Group Fail: {e}")
                        if photos:
                            try:
                                _tg_retry(bot.send_photo, cid, optimize_url(photos[0], width=1024), message_thread_id=tid)
                            except: pass
                    time.sleep(1.5) # SLEEP TO ENSURE MEDIA IS SENT BEFORE TEXT
                
                try:
                    sent_msg = _tg_retry(bot.send_message, cid, full_txt, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
                except Exception as e:
                    sent_msg = _tg_retry(bot.send_message, cid, full_txt.replace("<", "").replace(">", ""), message_thread_id=tid, reply_markup=markup)
                
                time.sleep(1.5) # SLEEP TO ENSURE NEXT APPLICATION DOES NOT OVERLAP
                if sent_msg:
                    supabase.table("casting_applications").update({"tg_message_id": sent_msg.message_id}).eq("id", app_id).execute()
                
            except Exception as e:
                print(f"Reload Item Error: {e}")

        # Check if more remain
        next_offset = offset + BATCH_SIZE
        if next_offset < total_count:
            # Send "Load More" button
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"🔄 Загрузить еще ({next_offset+1}-{min(next_offset+BATCH_SIZE, total_count)})", callback_data=f"reload_batch:{next_offset}"))
            
            if status_msg:
                _tg_retry(bot.delete_message, cid, status_msg.message_id)
            
            bot.send_message(cid, f"✅ Загружено {min(next_offset, total_count)} из {total_count}. Продолжить?", message_thread_id=tid, reply_markup=markup)
        else:
            if status_msg:
                _tg_retry(bot.delete_message, cid, status_msg.message_id)
            final_msg = bot.send_message(cid, f"✅ Все {total_count} анкет загружены.", message_thread_id=tid)
            auto_delete(final_msg, 5)

    except Exception as e:
        print(f"Process Batch Err: {e}")
        if status_msg:
             try: bot.edit_message_text(f"❌ Ошибка: {e}", cid, status_msg.message_id)
             except: pass

@bot.message_handler(commands=['doc'])
def handle_doc_command(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        if not tid:
            bot.reply_to(message, "⚠️ Команда работает только внутри топика.")
            return
            
        status_msg = bot.reply_to(message, "⏳ Поиск ВЫБРАННЫХ анкет...")
        
        # 1. Fetch apps for this topic
        apps = fetch_casting_applications(cid, tid)
        
        # 2. Filter SELECTED only (and deduplicate if needed)
        selected_apps = [a for a in apps if a.get('is_selected')]
        
        # Dedupe by phone (keep latest)
        unique_map = {}
        for app in selected_apps:
            key = app.get('phone') or app.get('instagram') or app.get('id')
            unique_map[key] = app
        
        final_list = sorted(unique_map.values(), key=lambda x: x.get('created_at'))
        
        if not final_list:
            bot.edit_message_text("⚠️ В этом топике нет выбранных анкет (с зеленой галочкой).", cid, status_msg.message_id)
            return
            
        count = len(final_list)
        bot.edit_message_text(f"⏳ Генерирую документ для {count} актеров...\n(Скачивание фото может занять время)", cid, status_msg.message_id)
        
        # 3. Generate DOCX
        target_name = final_list[0].get('casting_target', message.chat.title or "Casting")
        doc_io = generate_casting_docx(final_list, target_name)
        
        # Sanitize filename
        clean_name = re.sub(r'[^\w\s-]', '', target_name).strip().replace(' ', '_')
        if not clean_name: clean_name = "Selection"
        doc_io.name = f"{clean_name}_{datetime.now().strftime('%Y-%m-%d')}.docx"
        
        # 4. Send
        bot.send_chat_action(cid, 'upload_document', message_thread_id=tid)
        bot.send_document(cid, doc_io, message_thread_id=tid, caption=f"✅ Кастинг-лист: {target_name} ({count} чел.)")
        
        try: bot.delete_message(cid, status_msg.message_id)
        except: pass
        
    except Exception as e:
        print(f"DOC Error: {e}")
        try: bot.edit_message_text(f"❌ Ошибка генерации: {e}", cid, status_msg.message_id)
        except: pass

@bot.message_handler(commands=['reload'])
def handle_reload_command(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        # DEBUG: Verify we are here
        print(f"🔥 RELOAD COMMAND CAUGHT! Chat: {cid}, Thread: {tid}")

        if not tid:
            bot.reply_to(message, "⚠️ /reload работает только внутри топика.")
            return
        
        # Send immediate acknowledgment
        status_msg = bot.reply_to(message, "⏳ Поиск анкет...")
        
        # Start Batch 0 in a background thread to prevent webhook timeouts
        threading.Thread(target=process_reload_batch, args=(cid, tid, 0, status_msg)).start()
        
    except Exception as e:
        print(f"RELOAD FATAL: {e}")
        try: bot.reply_to(message, f"❌ Критическая ошибка: {e}")
        except: pass

@bot.message_handler(func=lambda m: m.text and (m.text.lower() == "!reload" or m.text.lower() == "релоад"))
def handle_reload_text_trigger(message):
    handle_reload_command(message)

@app.route('/api/reload', methods=['POST', 'OPTIONS'])
def reload_casting_endpoint():
    """
    Force reload of ALL applications for a specific chat/thread.
    Useful if bot failed to send messages or if chat history was cleared manually.
    """
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        data = request.json or {}
        cid = data.get('chat_id')
        tid = data.get('thread_id')
        
        # Validate CID/TID
        try:
            cid = int(cid)
            tid = int(tid) if tid and str(tid).isdigit() and int(tid) > 0 else None
        except:
            return jsonify({'error': 'Invalid chat_id or thread_id'}), 400
            
        print(f"🔄 RELOAD REQUEST for CID={cid}, TID={tid}")
        
        apps = fetch_casting_applications(cid, tid)
        if not apps:
            return jsonify({'status': 'empty', 'message': 'No applications found'}), 200
            
        found_count = len(apps)
        sent_count = 0
        
        for app_data in apps:
            try:
                app_id = app_data.get('id')
                safe_app = dict(app_data)
                photos = _normalize_url_list(safe_app.get("photo_urls"))
                safe_app["photo_urls"] = photos[:5]

                # Prepare Media
                media = []
                for i, url in enumerate(photos[:3]):
                    opt_url = optimize_url(url, width=1024)
                    media.append(types.InputMediaPhoto(opt_url))

                full_txt = format_casting_message(safe_app, is_selected=safe_app.get('is_selected', False))

                markup = types.InlineKeyboardMarkup()
                select_btn_text = "✅ ВЫБРАН" if safe_app.get('is_selected', False) else "ВЫБРАТЬ"
                markup.add(
                    types.InlineKeyboardButton(select_btn_text, callback_data=f"app_sel:{app_id}"),
                    types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
                )

                sent_msg = None
                
                if media:
                    try:
                        _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
                    except Exception as e:
                        if photos:
                            try: _tg_retry(bot.send_photo, cid, optimize_url(photos[0], width=1024), message_thread_id=tid)
                            except: pass
                    time.sleep(1.5)
                
                try: sent_msg = _tg_retry(bot.send_message, cid, full_txt, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
                except Exception: sent_msg = _tg_retry(bot.send_message, cid, full_txt.replace("<", "").replace(">", ""), message_thread_id=tid, reply_markup=markup)
                
                time.sleep(1.5)
                if sent_msg:
                    supabase.table("casting_applications").update({"tg_message_id": sent_msg.message_id}).eq("id", app_id).execute()
                    sent_count += 1
                
            except Exception as e:
                print(f"Failed to reload app {app_data.get('id')}: {e}")
                
        return jsonify({'status': 'ok', 'found_count': found_count, 'reloaded_count': sent_count}), 200

    except Exception as e:
        print(f"Reload Error: {e}")
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