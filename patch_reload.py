with open('api/index.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update process_reload_batch logic to do aggressive cleanup and deduplication
old_reload = """    try:
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

        # Deduplicate
        unique_map = {}
        for app in all_apps:
            phone = app.get('phone')
            key = phone if (phone and len(str(phone)) > 5) else (app.get('instagram') or app.get('id'))
            unique_map[key] = app

        clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))
        total_count = len(clean_apps)"""

new_reload = """    try:
        BATCH_SIZE = 10

        # 1. Fetch ALL apps for this chat/thread
        all_apps = fetch_casting_applications(cid, tid)
        if not all_apps:
            if status_msg:
                _tg_retry(bot.edit_message_text, f"⚠️ Анкет не найдено.", cid, status_msg.message_id)
            return

        # 2. Aggressive deduplication and Cleanup (Only on offset 0)
        if offset == 0:
            if status_msg:
                _tg_retry(bot.edit_message_text, "🧹 Очистка старых сообщений и дублей в этом топике...", cid, status_msg.message_id)

            unique_map = {}
            for app in all_apps:
                phone = app.get('phone')
                key = phone if (phone and len(str(phone)) > 5) else (app.get('instagram') or app.get('id'))

                # Try to delete old messages from Telegram to clear the topic
                old_msg_id = app.get('tg_message_id')
                if old_msg_id:
                    try:
                        media_ids = app.get('media_message_ids') or []
                        photos = _normalize_url_list(app.get('photo_urls'))
                        video = app.get('video_audition_url')
                        mc = min(len(photos) + (1 if video else 0), 10)
                        all_ids_to_del = [old_msg_id] + media_ids if media_ids else None
                        safe_delete_messages(cid, old_msg_id, mc, all_ids_to_del)
                    except Exception as e:
                        print(f"Cleanup TG error: {e}")

                if key in unique_map:
                    # Merge media into the newest record (the one we keep)
                    existing = unique_map[key]

                    # Determine which is newer
                    current_is_newer = app.get('created_at', '') > existing.get('created_at', '')

                    newer_app = app if current_is_newer else existing
                    older_app = existing if current_is_newer else app

                    # Merge
                    n_photos = _normalize_url_list(newer_app.get('photo_urls'))
                    o_photos = _normalize_url_list(older_app.get('photo_urls'))
                    merged_photos = list(dict.fromkeys(n_photos + o_photos))

                    newer_app['photo_urls'] = ",".join(merged_photos) if merged_photos else None
                    if not newer_app.get('video_audition_url'):
                        newer_app['video_audition_url'] = older_app.get('video_audition_url')
                    if not newer_app.get('portfolio_url'):
                        newer_app['portfolio_url'] = older_app.get('portfolio_url')

                    # Delete the older record from DB
                    try:
                        supabase.table("casting_applications").delete().eq("id", older_app.get('id')).execute()
                    except: pass

                    # Update the newer record in DB with merged media
                    try:
                        supabase.table("casting_applications").update({
                            "photo_urls": newer_app['photo_urls'],
                            "video_audition_url": newer_app['video_audition_url'],
                            "portfolio_url": newer_app['portfolio_url'],
                            "tg_message_id": None, # Reset msg ID since we deleted it
                            "media_message_ids": None
                        }).eq("id", newer_app.get('id')).execute()
                    except: pass

                    unique_map[key] = newer_app
                else:
                    # Update DB to clear msg IDs just in case
                    try:
                        supabase.table("casting_applications").update({
                            "tg_message_id": None,
                            "media_message_ids": None
                        }).eq("id", app.get('id')).execute()
                    except: pass
                    unique_map[key] = app

            # Refresh list after deduplication
            clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))
        else:
            # For offsets > 0, just use the fetched list assuming it was already deduplicated
            # Wait, fetch_casting_applications will still fetch everything. We need to dedupe in memory
            # without triggering deletes again.
            unique_map = {}
            for app in all_apps:
                phone = app.get('phone')
                key = phone if (phone and len(str(phone)) > 5) else (app.get('instagram') or app.get('id'))
                # Just keep the newest in memory for pagination
                if key in unique_map:
                    if app.get('created_at', '') > unique_map[key].get('created_at', ''):
                        unique_map[key] = app
                else:
                    unique_map[key] = app
            clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))

        total_count = len(clean_apps)"""

code = code.replace(old_reload, new_reload)

# Update send_casting_application_message to ensure correct media order (Photo -> Text)
old_send = """    try:
        app_id = app_data.get('id')
        safe_app = dict(app_data)
        photos = _normalize_url_list(safe_app.get("photo_urls"))
        safe_app["photo_urls"] = photos

        # Prepare Media
        media = []
        for i, url in enumerate(photos[:3]):
            opt_url = optimize_url(url, width=800)
            if i == 0:
                caption = f"📸 <b>{safe_app.get('full_name')}</b>\\n{safe_app.get('casting_target')}\\n⬇️ Описание ниже"


                media.append(types.InputMediaPhoto(opt_url, caption=caption, parse_mode="HTML"))
            else:
                media.append(types.InputMediaPhoto(opt_url))

        # Send Media Group
        if media:
            try:
                _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
            except Exception as e:
                print(f"Send Media Group Fail: {e}")
                if photos:
                    try:
                        _tg_retry(bot.send_photo, cid, optimize_url(photos[0], width=800), message_thread_id=tid)
                    except: pass

        full_txt = format_casting_message(safe_app, is_selected=safe_app.get('is_selected', False))

        markup = types.InlineKeyboardMarkup()
        sel_txt = "✅ ВЫБРАН" if safe_app.get('is_selected') else "ВЫБРАТЬ"
        markup.add(
            types.InlineKeyboardButton(sel_txt, callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
        )

        sent_msg = None
        try:
            sent_msg = _tg_retry(bot.send_message, cid, full_txt, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            sent_msg = _tg_retry(bot.send_message, cid, full_txt.replace("<", "").replace(">", ""), message_thread_id=tid, reply_markup=markup)

        if sent_msg:
            supabase.table("casting_applications").update({"tg_message_id": sent_msg.message_id}).eq("id", app_id).execute()
    except Exception as e:
        print(f"Send Item Error: {e}")"""

new_send = """    try:
        app_id = app_data.get('id')
        safe_app = dict(app_data)
        photos = _normalize_url_list(safe_app.get("photo_urls"))
        video_url = safe_app.get("video_audition_url")
        safe_app["photo_urls"] = photos

        # Prepare Media (Max 3 photos, 1 video)
        media = []
        media_message_ids = []

        # Add up to 3 photos
        for i, url in enumerate(photos[:3]):
            opt_url = optimize_url(url, width=800)
            if i == 0:
                caption = f"📸 <b>{safe_app.get('full_name')}</b>\\n{safe_app.get('casting_target')}\\n⬇️ Описание ниже"
                media.append(types.InputMediaPhoto(opt_url, caption=caption, parse_mode="HTML"))
            else:
                media.append(types.InputMediaPhoto(opt_url))

        # Add 1 video if available
        if video_url:
            media.append(types.InputMediaVideo(video_url))

        # Send Media Group
        if media:
            try:
                media_msgs = _tg_retry(bot.send_media_group, cid, media, message_thread_id=tid)
                if media_msgs:
                    media_message_ids = [m.message_id for m in media_msgs]
            except Exception as e:
                print(f"Send Media Group Fail: {e}")
                # Fallback to single photo if group fails
                if photos:
                    try:
                        m = _tg_retry(bot.send_photo, cid, optimize_url(photos[0], width=800), message_thread_id=tid)
                        if m: media_message_ids = [m.message_id]
                    except: pass

        # Send Text Profile
        full_txt = format_casting_message(safe_app, is_selected=safe_app.get('is_selected', False))

        markup = types.InlineKeyboardMarkup()
        sel_txt = "✅ ВЫБРАН" if safe_app.get('is_selected') else "ВЫБРАТЬ"
        markup.add(
            types.InlineKeyboardButton(sel_txt, callback_data=f"app_sel:{app_id}"),
            types.InlineKeyboardButton("🗑️ УДАЛИТЬ", callback_data=f"app_del:{app_id}")
        )

        sent_msg = None
        try:
            sent_msg = _tg_retry(bot.send_message, cid, full_txt, message_thread_id=tid, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            sent_msg = _tg_retry(bot.send_message, cid, full_txt.replace("<", "").replace(">", ""), message_thread_id=tid, reply_markup=markup)

        if sent_msg:
            update_data = {"tg_message_id": sent_msg.message_id}
            if media_message_ids:
                update_data["media_message_ids"] = media_message_ids
            supabase.table("casting_applications").update(update_data).eq("id", app_id).execute()
    except Exception as e:
        print(f"Send Item Error: {e}")"""

code = code.replace(old_send, new_send)

with open('api/index.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched reload and send logics")
