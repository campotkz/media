import re

with open('api/index.py', 'r') as f:
    content = f.read()

# Normalize phone function to use in python
norm_func = """
def _normalize_phone(p):
    if not p: return ""
    p = str(p)
    return re.sub(r'\\D', '', p)
"""

if "_normalize_phone" not in content:
    content = content.replace("def process_reload_batch", norm_func + "\ndef process_reload_batch")


# Update process_reload_batch deduplication logic
dedup_old = """        # Deduplicate
        unique_map = {}
        for app in all_apps:
            phone = app.get('phone')
            key = phone if (phone and len(str(phone)) > 5) else (app.get('instagram') or app.get('id'))
            unique_map[key] = app

        clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))"""

dedup_new = """        # Deduplicate: Group by normalized phone or instagram, take LATEST
        unique_map = {}
        for app in all_apps:
            phone = _normalize_phone(app.get('phone'))
            key = phone if phone and len(phone) > 5 else (app.get('instagram') or app.get('id'))
            if key in unique_map:
                if app.get('created_at', '') > unique_map[key].get('created_at', ''):
                    unique_map[key] = app
            else:
                unique_map[key] = app

        clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))"""

content = content.replace(dedup_old, dedup_new)

# Add Video to Media logic
media_old = """                # Prepare Media
                media = []
                for i, url in enumerate(photos[:3]):
                    opt_url = optimize_url(url, width=1024)
                    if i == 0:
                        caption = f"📸 <b>{safe_app.get('full_name')}</b>\\n{safe_app.get('casting_target')}\\n⬇️ Описание ниже"
                        media.append(types.InputMediaPhoto(opt_url, caption=caption, parse_mode="HTML"))
                    else:
                        media.append(types.InputMediaPhoto(opt_url))"""

media_new = """                # Prepare Media
                media = []
                # First up to 3 photos
                for i, url in enumerate(photos[:3]):
                    opt_url = optimize_url(url, width=1024)
                    if i == 0:
                        caption = f"📸 <b>{safe_app.get('full_name')}</b>\\n{safe_app.get('casting_target')}\\n⬇️ Описание ниже"
                        media.append(types.InputMediaPhoto(opt_url, caption=caption, parse_mode="HTML"))
                    else:
                        media.append(types.InputMediaPhoto(opt_url))

                # And one video if present
                video = safe_app.get('video_audition_url')
                if video:
                    if not media:
                        caption = f"🎬 <b>{safe_app.get('full_name')}</b>\\n{safe_app.get('casting_target')}\\n⬇️ Описание ниже"
                        media.append(types.InputMediaVideo(video, caption=caption, parse_mode="HTML"))
                    else:
                        media.append(types.InputMediaVideo(video))"""

content = content.replace(media_old, media_new)

# Add Cleanup logic to handle_reload_command
reload_old = """        # Send immediate acknowledgment
        status_msg = bot.reply_to(message, "⏳ Поиск анкет...")"""

reload_new = """        # Send immediate acknowledgment
        status_msg = bot.reply_to(message, "⏳ Очистка топика и поиск анкет...")

        # CLEAR CURRENT TOPIC OLD MESSAGES
        try:
            # Find all message IDs for this chat & thread
            old_res = supabase.table("casting_applications").select("tg_message_id, photo_urls, video_audition_url").eq("chat_id", cid).eq("thread_id", tid).not_.is_("tg_message_id", "null").execute()
            if old_res.data:
                for old_app in old_res.data:
                    old_msg_id = old_app.get("tg_message_id")
                    if old_msg_id:
                        try: bot.delete_message(cid, old_msg_id)
                        except: pass

                        media_count = len(old_app.get('photo_urls') or [])
                        if old_app.get('video_audition_url'): media_count += 1
                        media_count = min(media_count, 10)
                        for i in range(1, media_count + 1):
                            try: bot.delete_message(cid, int(old_msg_id) - i)
                            except: pass
        except Exception as cl_err:
            print(f"Cleanup Err: {cl_err}")"""

content = content.replace(reload_old, reload_new)


with open('api/index.py', 'w') as f:
    f.write(content)
