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
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
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
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Version indicator for debugging
VERSION = "1.7.1 (Backported & Merged)"

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
        
    # Standardize video field (handle video_url and video_audition_url)
    v_url = data.get('video_url') or data.get('video_audition_url')
    if v_url:
        full_txt += f"🎥 <a href='{v_url}'>Видеовизитка</a>\n"
        
    # Get photos (handle string or list)
    photos = data.get('photo_urls', [])
    if isinstance(photos, str) and photos.strip():
        if photos.startswith('[') and photos.endswith(']'):
            import json
            try: photos = json.loads(photos)
            except: photos = photos.split(',')
        else:
            photos = [p.strip() for p in photos.split(',') if p.strip()]
        
    # If there are more than 3 photos, add links to the rest
    if isinstance(photos, list) and len(photos) > 3:
        full_txt += "\n🖼 <b>Дополнительные фото:</b>\n"
        for i, url in enumerate(photos[3:], 1):
            full_txt += f"• <a href='{url}'>Фото {i+3}</a>\n"
            
    return full_txt# --- Database & Migration ---
# --- Helpers ---

def ensure_project(chat_id, thread_id, chat_title, forced_name=None):
    """
    Ensures a project (client) exists in the database for the given chat and thread.
    Creates it if it doesn't exist.
    """
    if not thread_id:
        return

    try:
        # Check if exists
        res = supabase.from_("clients").select("id").eq("chat_id", chat_id).eq("thread_id", thread_id).execute()
        if not res.data:
            # Create new
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

# Global executor to prevent thread leaking during warm starts in Vercel
_bg_executor = ThreadPoolExecutor(max_workers=3)

def auto_delete(msg, delay=10):
    """
    Schedules a message for deletion. In Vercel serverless, Threading may fail.
    We will use a short time.sleep in a global ThreadPoolExecutor as best-effort.
    """
    if not msg:
        return

    def _delete():
        time.sleep(min(delay, 5)) # Cap delay to 5 seconds to reduce risk of Vercel kill
        try:
            bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass

    try:
        _bg_executor.submit(_delete)
    except Exception as e:
        print(f"auto_delete err: {e}")

def _tg_retry(fn, *args, **kwargs):
    for i in range(3): # Reduce from 100 to 3 for serverless safety
        try:
            return fn(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 429:
                # Use retry_after if provided, otherwise 1s
                wait = e.result_json.get('parameters', {}).get('retry_after', 1) + 1
                if wait > 5: wait = 5 # Cap it to keep it within Vercel limits
                time.sleep(wait)
            else: raise
        except Exception as e:
            print(f"⚠️ TG Retry Drop {i+1}/3: {e}")
            if i == 2: raise
            time.sleep(1) # Faster retry
    return None


# --- Media Offloading ---

def offload_media_to_telegram(app_id, data):
    """Переносит фото из Supabase в TG канал для экономии места.
    Использует батчинг через send_media_group для ускорения."""
    try:
        print(f"🚀 Starting background offload for App ID: {app_id}")
        photos = _normalize_url_list(data.get('photo_urls'))
        video = data.get('video_audition_url')
        new_photos, new_video = [], video

        if photos:
            # Separate supabase URLs from others
            supa_photos = [url for url in photos if 'supabase' in url]
            other_photos = [url for url in photos if 'supabase' not in url]
            new_photos.extend(other_photos)

            # Batch upload Supabase photos in chunks of up to 10
            for i in range(0, len(supa_photos), 10):
                batch = supa_photos[i:i+10]
                if len(batch) == 1:
                    # Single photo fallback
                    msg = _tg_retry(bot.send_photo, MEDIA_CHANNEL_ID, optimize_url(batch[0]), disable_notification=True)
                    if msg:
                        new_photos.append(f"tg://{msg.photo[-1].file_id}")
                        print(f"✅ Photo offloaded (single): {batch[0]}")
                elif len(batch) > 1:
                    # Media group (2-10 photos)
                    media_group = [types.InputMediaPhoto(optimize_url(url)) for url in batch]
                    try:
                        msgs = _tg_retry(bot.send_media_group, MEDIA_CHANNEL_ID, media_group, disable_notification=True)
                        if msgs:
                            for msg, orig_url in zip(msgs, batch):
                                new_photos.append(f"tg://{msg.photo[-1].file_id}")
                                print(f"✅ Photo offloaded (batch): {orig_url}")
                    except Exception as me:
                        print(f"⚠️ Batch offload failed: {me}. Falling back to single uploads.")
                        for url in batch:
                            msg = _tg_retry(bot.send_photo, MEDIA_CHANNEL_ID, optimize_url(url), disable_notification=True)
                            if msg: new_photos.append(f"tg://{msg.photo[-1].file_id}")
        
        if video and 'supabase' in video:
            msg = _tg_retry(bot.send_video, MEDIA_CHANNEL_ID, video, disable_notification=True)
            if msg: 
                new_video = f"tg://{msg.video.file_id}"
                print(f"✅ Video offloaded: {video}")

        # Preserve the original order if needed, but since we separated them, it's ok as long as all are saved
        update_payload = {
            "photo_urls": new_photos, 
            "video_audition_url": new_video
        }
        res = supabase.table('casting_applications').update(update_payload).eq('id', app_id).execute()
        print(f"✅ App {app_id} updated with TG media IDs. Status: {res.data is not None}")
        data.update(update_payload)
    except Exception as e:
        print(f"❌ Offload FATAL Error for App {app_id}: {e}")
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

@app.route('/api/timer/report', methods=['POST', 'OPTIONS'])
def submit_timer_report():
    if request.method == 'OPTIONS':
        r = app.make_response('')
        r.headers.add('Access-Control-Allow-Origin', '*')
        r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        r.headers.add('Access-Control-Allow-Methods', 'POST')
        return r
    try:
        # Expected from timer.html: {"shift_id": ..., "chat_id": ..., "thread_id": ...}
        # Acknowledges and returns status ok
        r = jsonify({'status': 'ok'})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r
    except Exception as e:
        r = jsonify({'error': str(e)})
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r, 500

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

MAX_BASE64_LENGTH = 15 * 1024 * 1024 # 15MB

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

        if len(base64_data) > MAX_BASE64_LENGTH:
            return jsonify({'error': 'Payload too large'}), 413

        # Find target chat/thread from database
        res = supabase.from_("clients").select("chat_id, thread_id").eq("name", project_name).execute()
        if not res.data:
            return jsonify({'error': f'Project "{project_name}" not found in database'}), 404
        
        target = res.data[0]
        chat_id = target.get('chat_id')
        thread_id = target.get('thread_id')

        if not chat_id:
            return jsonify({'error': f'Project "{project_name}" has no linked chat_id'}), 400

        # Decode base64 file with padding fix
        # Ensure proper padding to avoid binascii.Error
        padding_needed = len(base64_data) % 4
        if padding_needed:
            base64_data += '=' * (4 - padding_needed)

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
        
        if tid is None:
            bot.reply_to(message, "❌ Эту команду можно использовать только внутри топика проекта.")
            return

        new_name = (message.text or "").replace('/rename', '').strip()
        if not new_name:
            bot.reply_to(message, "📝 Напишите новое название после команды. Пример: `/rename Проект А`", parse_mode="Markdown")
            return
        
        # Determine category from chat title (group name)
        chat_title = message.chat.title or ""
        category = 'casting' if 'КАСТИНГ' in chat_title.upper() else 'media'
        
        # Attempt to rename topic (bot must be admin)
        try:
            bot.edit_forum_topic(cid, tid, name=new_name)
        except Exception as e:
            print(f"Failed to rename forum topic (bot might not be admin): {e}")

        # 1. Update existing
        res = supabase.from_("clients").update({"name": new_name, "category": category}).eq("chat_id", cid).eq("thread_id", tid).execute()
        
        # 2. If no rows updated, create it with the correct name and category
        if not res.data:
            ensure_project(cid, tid, chat_title, forced_name=new_name)
            bot.reply_to(message, f"✅ Проект создан и назван: **{new_name}**")
        else:
            bot.reply_to(message, f"✅ Топик переименован: **{new_name}** и обновлен в базе.")
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

@bot.message_handler(commands=['del'])
def handle_delete(message):
    try:
        cid = message.chat.id
        tid = message.message_thread_id
        
        # 1. CONTEXTUAL MODE (Reply)
        if message.reply_to_message:
            reply = message.reply_to_message
            txt = (reply.text or reply.caption or "")
            
            # Check if it's an Application
            if "АНКЕТА:" in txt or (reply.reply_to_message and "АНКЕТА:" in (reply.reply_to_message.text or reply.reply_to_message.caption or "")):
                target_reply = reply
                if "АНКЕТА:" not in txt:
                    target_reply = reply.reply_to_message

                res = supabase.table("casting_applications").select("id").eq("tg_message_id", target_reply.message_id).execute()
                if res.data:
                    app_id = res.data[0]['id']
                    try: bot.delete_message(message.chat.id, message.message_id)
                    except: pass
                    # Reuse callback logic
                    handle_app_delete_callback(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0",
                                                                  message=target_reply, data=f"app_del:{app_id}"))
                    return

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
            else:
                bot.reply_to(message, "❌ Пожалуйста, отвечайте именно на сообщение с АНКЕТОЙ или ссылками.")
        else:
            bot.reply_to(message, "❌ Пожалуйста, используйте **ОТВЕТ** на сообщение для удаления.")
    except Exception as e:
        print(f"Delete Error: {e}")
    return False

# --- Webhook Routes ---

@app.route('/api/casting', methods=['POST', 'OPTIONS'])
def notify_casting():
    if request.method == 'OPTIONS': return ('', 204)
    try:
        data = request.json or {}
        cid = int(data.get('chat_id', 0))
        tid = int(data.get('thread_id', 0)) if data.get('thread_id') else None
        
        # Normalize application ID
        app_id = data.get('id') or data.get('application_id')
        if not app_id:
            # Try to find by phone if missing
            phone = data.get('phone')
            if phone:
                res = supabase.table("casting_applications").select("id").eq("phone", phone).order("created_at", desc=True).limit(1).execute()
                if res.data: app_id = res.data[0]['id']
        
        if not cid: return jsonify({'error': 'no chat_id provided'}), 400

        # Identifiers for deduplication/blacklist
        phone = data.get('phone')
        insta = data.get('instagram')

        # 1. QUICK BLACKLIST CHECK
        try:
            if phone or insta:
                bl_query = supabase.table("blacklist").select("id")
                if phone and insta: bl_query = bl_query.or_(f"phone.eq.{phone},instagram.eq.{insta}")
                elif phone: bl_query = bl_query.eq("phone", phone)
                elif insta: bl_query = bl_query.eq("instagram", insta)
                
                bl_res = bl_query.execute()
                if bl_res.data:
                    return jsonify({'status': 'blocked', 'message': 'User is blacklisted'}), 200
        except Exception as bl_err:
            print(f"⚠️ Blacklist Check Failed: {bl_err}")

        # 2. DEDUPLICATION (Synchronous but fast)
        try:
            n_phone = normalize_phone(phone)
            n_insta = normalize_insta(insta)
            if n_phone or n_insta:
                query = supabase.table("casting_applications").select("id, tg_message_id, media_message_ids").eq("chat_id", cid)
                if tid: query = query.eq("thread_id", tid)
                conds = []
                if n_phone and len(n_phone) > 5: conds.append(f"phone.eq.{n_phone}")
                if n_insta and len(n_insta) > 2: conds.append(f"instagram.eq.{n_insta}")
                if conds:
                    query = query.or_(",".join(conds))
                    if app_id: query = query.neq("id", app_id)
                    old_res = query.execute()
                    if old_res.data:
                        for old_app in old_res.data:
                            # Delete old text message
                            old_msg_id = old_app.get('tg_message_id')
                            if old_msg_id:
                                try: bot.delete_message(cid, old_msg_id)
                                except: pass
                            # Delete old media group
                            old_media_ids = old_app.get('media_message_ids') or []
                            for mid in old_media_ids:
                                try: bot.delete_message(cid, mid)
                                except: pass
                            # Delete from DB
                            supabase.table("casting_applications").delete().eq("id", old_app.get('id')).execute()
        except Exception as de: print(f"Dedup Err: {de}")

        # 3. FORMAT & SEND CORE TELEGRAM MESSAGE (Synchronous)
        text = format_casting_message(data)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ ВЫБРАТЬ", callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
        )

        photos = _normalize_url_list(data.get('photo_urls'))
        media_ids = []
        reply_to = None
        
        # Send up to 3 photos immediately (Sync)
        if photos:
            media = []
            for i, p_url in enumerate(photos[:3]):
                url = p_url.replace('tg://', '') if p_url.startswith('tg://') else p_url
                # No long caption here, just name
                media.append(types.InputMediaPhoto(url, caption=f"📸 {data.get('full_name')}"))
            try:
                sent_group = _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
                if sent_group: 
                    media_ids = [m.message_id for m in sent_group]
                    reply_to = sent_group[0].message_id
            except Exception as me: print(f"Media Group Err: {me}")
            time.sleep(0.5)

        # Main message (Sync)
        try:
            sent_msg = _tg_retry(bot.send_message, cid, text, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", reply_to_message_id=reply_to)
        except Exception as te:
            # Fallback for hidden/deleted topics
            if "thread not found" in str(te).lower() and tid is not None:
                sent_msg = _tg_retry(bot.send_message, cid, text, reply_markup=markup, parse_mode="HTML", reply_to_message_id=reply_to)
            else:
                raise te
        
        if sent_msg and app_id:
            # Update DB with message ID
            supabase.table("casting_applications").update({
                "tg_message_id": sent_msg.message_id,
                "media_message_ids": media_ids
            }).eq("id", app_id).execute()

        # 4. MEDIA OFFLOADING (Synchronous for Vercel stability)
        if app_id:
            offload_media_to_telegram(app_id, data)

        return jsonify({
            'status': 'ok', 
            'message': 'Casting notified successfully', 
            'msg_id': sent_msg.message_id if sent_msg else None,
            'app_id': app_id
        })

    except Exception as e:
        print(f"Casting API FATAL: {e}")
        # Return full error to help user debug the "Bot Notify warning" in console
        return jsonify({'error': f"CRITICAL: {str(e)}"}), 500

# --- DEPRECATED (Kept for reference or cleanup later) ---
    """DEPRECATED: Logic moved back to notify_casting to prevent Vercel process death."""
    pass


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
                import time
                def delayed_delete(chat_id, msg_id):
                    time.sleep(10)
                    try: bot.delete_message(chat_id, msg_id)
                    except: pass
                
                _bg_executor.submit(delayed_delete, cid, conf_msg.message_id)
            
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('reload_resume:'))
def handle_reload_resume(call):
    try:
        _, offset_str = call.data.split(':')
        offset = int(offset_str)
        cid, tid = call.message.chat.id, call.message.message_thread_id
        
        bot.edit_message_text(f"⏳ Загрузка с {offset} анкеты...", cid, call.message.message_id)
        
        if offset == 0:
            supabase.from_("clients").update({"reload_offset": 0}).eq("chat_id", cid).eq("thread_id", tid).execute()

        process_reload_batch(cid, tid, offset, call.message)
        
    except Exception as e:
        print(f"Reload Resume Err: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reload_batch:'))
def handle_reload_batch_callback(call):
    try:
        _, offset_str = call.data.split(':')
        offset = int(offset_str)
        cid, tid = call.message.chat.id, call.message.message_thread_id
        
        bot.answer_callback_query(call.id, "Загружаю следующую партию...")
        process_reload_batch(cid, tid, offset, call.message)
        
    except Exception as e:
        print(f"Reload Batch Err: {e}")

def process_reload_batch(cid, tid, offset=0, status_msg=None):
    try:
        BATCH_SIZE = 5
        all_apps = fetch_casting_applications(cid, tid)
        if not all_apps:
            if status_msg: _tg_retry(bot.edit_message_text, "⚠️ Анкет не найдено.", cid, status_msg.message_id)
            return

        # 2. Deduplicate
        unique_map = {}
        to_delete = []
        for app in sorted(all_apps, key=lambda x: x.get('created_at')):
            phone = normalize_phone(app.get('phone'))
            insta = normalize_insta(app.get('instagram'))
            key = phone if (phone and len(phone) > 5) else (insta or app.get('id'))
            if key in unique_map:
                to_delete.append(unique_map[key]['id'])
            unique_map[key] = app
            
        # Bulk Cleanup (Much faster)
        if to_delete:
            supabase.table("casting_applications").delete().in_("id", to_delete).execute()

        clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))
        total_count = len(clean_apps)
        batch = clean_apps[offset : offset + BATCH_SIZE]
        
        if not batch:
            if status_msg: _tg_retry(bot.edit_message_text, f"✅ Все анкеты загружены ({total_count}).", cid, status_msg.message_id)
            return

        if status_msg:
            _tg_retry(bot.edit_message_text, f"⏳ Загрузка {offset+1}-{min(offset+BATCH_SIZE, total_count)} из {total_count}...", cid, status_msg.message_id)
        
        # Check active state once per batch
        is_active = True
        if tid:
            cl_chk = supabase.from_("clients").select("is_active").eq("chat_id", cid).eq("thread_id", tid).execute()
            if cl_chk.data and cl_chk.data[0].get("is_active") is False: is_active = False

        if not is_active:
            if status_msg: bot.edit_message_text("🛑 Загрузка прервана.", cid, status_msg.message_id)
            return

        for i, app_data in enumerate(batch):
            try:
                # Media migration (Background/Sync)
                app_data = offload_media_to_telegram(app_data['id'], app_data)
                
                app_id = app_data.get('id')
                photos = _normalize_url_list(app_data.get("photo_urls"))
                media = [types.InputMediaPhoto(optimize_url(u, width=1024)) for u in photos[:3]]
                full_txt = format_casting_message(app_data, is_selected=app_data.get('is_selected', False))

                markup = types.InlineKeyboardMarkup()
                sel_t = "✅ ВЫБРАН" if app_data.get('is_selected') else "ВЫБРАТЬ"
                markup.add(
                    types.InlineKeyboardButton(sel_t, callback_data=f"app_sel:{app_id}"),
                    types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
                )

                media_ids = []
                reply_to = None
                if media:
                    try: 
                        sent_grp = _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
                        if sent_grp: 
                            media_ids = [m.message_id for m in sent_grp]
                            reply_to = sent_grp[0].message_id
                    except: pass
                    time.sleep(0.5) 
                
                try: 
                    sent_msg = _tg_retry(bot.send_message, cid, full_txt, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True, reply_to_message_id=reply_to)
                except: 
                    sent_msg = _tg_retry(bot.send_message, cid, full_txt.replace("<","").replace(">",""), message_thread_id=tid, reply_markup=markup, reply_to_message_id=reply_to)
                
                time.sleep(0.5)
                if sent_msg:
                    supabase.table("casting_applications").update({
                        "tg_message_id": sent_msg.message_id,
                        "media_message_ids": media_ids
                    }).eq("id", app_id).execute()
            except Exception as item_e:
                print(f"Reload Item Error: {item_e}")
                continue

        # Check if more remain
        next_offset = offset + BATCH_SIZE
        if next_offset < total_count:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"🔄 Загрузить еще ({next_offset+1}-{min(next_offset+BATCH_SIZE, total_count)})", callback_data=f"reload_batch:{next_offset}"))
            
            if tid:
                supabase.from_("clients").update({"reload_offset": next_offset}).eq("chat_id", cid).eq("thread_id", tid).execute()
            
            if status_msg: _tg_retry(bot.delete_message, cid, status_msg.message_id)
            bot.send_message(cid, f"✅ Загружено {min(next_offset, total_count)} из {total_count}. Продолжить?", message_thread_id=tid, reply_markup=markup)
        else:
            if tid:
                supabase.from_("clients").update({"reload_offset": 0}).eq("chat_id", cid).eq("thread_id", tid).execute()
            if status_msg: _tg_retry(bot.delete_message, cid, status_msg.message_id)
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
        # 1. Immediate acknowledgment so user knows bot isn't "hanging"
        init_msg = bot.reply_to(message, "⏳ Подключаюсь к базе данных...")
        
        cid = message.chat.id
        tid = message.message_thread_id
        
        # 2. Check existing offset in DB with safety
        offset = 0
        try:
            res = supabase.from_("clients").select("reload_offset").eq("chat_id", cid).eq("thread_id", tid).execute()
            if res.data and res.data[0].get("reload_offset"):
                offset = res.data[0].get("reload_offset")
        except Exception as db_e:
            print(f"DB Offset Check Error: {db_e}")
            # Fallback to 0 if DB check fails

        if offset > 0:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("▶️ Продолжить", callback_data=f"reload_resume:{offset}"),
                types.InlineKeyboardButton("🔄 Начать заново", callback_data="reload_resume:0")
            )
            bot.edit_message_text(f"⚠️ У вас есть прерванная загрузка (остановлено на {offset} анкете).\nВыберите действие:", cid, init_msg.message_id, reply_markup=markup)
            return
        
        # 3. Update init message
        bot.edit_message_text("⏳ Поиск анкет...", cid, init_msg.message_id)
        status_msg = init_msg
        
        # Start Batch 0 synchronously for Vercel stability
        process_reload_batch(cid, tid, 0, status_msg)
        
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
            
        print(f"🔄 RELOAD API for CID={cid}, TID={tid}")
        
        # Process synchronously for Vercel stability
        process_reload_batch(cid, tid, 0)
        
        return jsonify({
            'status': 'ok', 
            'message': 'Reload started in background'
        }), 200

    except Exception as e:
        print(f"Reload Error: {e}")
        return jsonify({'error': str(e)}), 500

def cors_response():
    # Helper for legacy routes, though after_request handles most things now
    return ('', 204)

# --- Bot Handlers ---


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

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_del:'))
def handle_app_delete_callback(call):
    try:
        app_id = call.data.split(':')[1]
        cid, tid = call.message.chat.id, call.message.message_thread_id
        
        # 1. Fetch data for deletion
        res = supabase.table("casting_applications").select("*").eq("id", app_id).execute()
        if not res.data:
            bot.answer_callback_query(call.id, "❌ Анкета уже удалена")
            try: bot.delete_message(cid, call.message.message_id)
            except: pass
            return

        app_data = res.data[0]
        msg_id = app_data.get('tg_message_id')
        media_group = app_data.get('media_message_ids') or []

        # 2. Delete from DB first
        supabase.table("casting_applications").delete().eq("id", app_id).execute()
        
        # 3. Delete Telegram messages
        # Delete text application
        if msg_id:
            try: bot.delete_message(cid, msg_id)
            except: pass
            
        # Delete media group
        for mid in media_group:
            try: bot.delete_message(cid, mid)
            except: pass

        # Delete the button message itself if it's different (e.g. confirmation message in forward sync)
        if call.message.message_id != msg_id:
            try: bot.delete_message(cid, call.message.message_id)
            except: pass

        bot.answer_callback_query(call.id, "✅ Анкета удалена")

    except Exception as e:
        print(f"Delete Error: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка удаления: {e}", show_alert=True)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))