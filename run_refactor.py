import re

with open('api/index.py', 'r') as f:
    content = f.read()

helper_funcs = """
def _check_blacklist(phone, insta, supabase_client):
    try:
        if phone or insta:
            bl_query = supabase_client.table("blacklist").select("id")
            if phone and insta:
                bl_query = bl_query.or_(f"phone.eq.{phone},instagram.eq.{insta}")
            elif phone:
                bl_query = bl_query.eq("phone", phone)
            elif insta:
                bl_query = bl_query.eq("instagram", insta)

            bl_res = bl_query.execute()
            if bl_res.data:
                print(f"🚫 BLOCKED: Application from {phone}/{insta} is in Blacklist.")
                return True, {'status': 'blocked', 'message': 'User is blacklisted'}
    except Exception as bl_err:
        print(f"⚠️ Blacklist Check Failed: {bl_err}")
        if "relation \\"public.blacklist\\" does not exist" in str(bl_err) or "404" in str(bl_err):
            ensure_blacklist_table()
    return False, None

def _cleanup_previous_application(app_id, cid, supabase_client, bot_client):
    if not app_id: return
    try:
        self_res = supabase_client.table("casting_applications").select("tg_message_id, photo_urls, video_audition_url").eq("id", app_id).single().execute()
        if self_res.data:
            old_msg_id = self_res.data.get('tg_message_id')
            if old_msg_id:
                print(f"🔄 Self-Cleanup: Deleting old message {old_msg_id} for app {app_id}")
                try:
                    bot_client.delete_message(cid, old_msg_id)
                    media_count = len(self_res.data.get('photo_urls') or [])
                    if self_res.data.get('video_audition_url'): media_count += 1
                    media_count = min(media_count, 10)
                    for i in range(1, media_count + 1):
                        try: bot_client.delete_message(cid, int(old_msg_id) - i)
                        except: pass
                except Exception as e:
                    print(f"⚠️ Self-Cleanup Failed (msg too old?): {e}")
    except Exception as e:
        print(f"⚠️ Self-Cleanup Error: {e}")

def _remove_duplicate_applications(data, cid, tid, phone, insta, app_id, supabase_client, bot_client):
    try:
        query = supabase_client.table("casting_applications").select("id, tg_message_id, photo_urls, video_audition_url")
        query = query.eq("chat_id", cid)
        if tid: query = query.eq("thread_id", tid)

        conditions = []
        if phone and len(str(phone)) > 5: conditions.append(f"phone.eq.{phone}")
        if insta and len(str(insta)) > 2: conditions.append(f"instagram.eq.{insta}")

        if conditions: query = query.or_(",".join(conditions))
        else:
            print("⚠️ Deduplication skipped: No valid phone or instagram to match.")
            return

        if app_id: query = query.neq("id", app_id)

        old_res = query.not_.is_("tg_message_id", "null").order("created_at", descending=True).execute()

        if old_res.data:
            for old_app in old_res.data:
                old_msg_id = old_app.get('tg_message_id')
                old_db_id = old_app.get('id')
                print(f"🗑️ Found duplicate: {old_db_id} (msg: {old_msg_id})")

                if old_msg_id:
                    try:
                        bot_client.delete_message(cid, old_msg_id)
                        print(f"   Deleted text msg {old_msg_id}")
                        media_count = len(old_app.get('photo_urls') or [])
                        if old_app.get('video_audition_url'): media_count += 1
                        media_count = min(media_count, 10)

                        print(f"   Attempting to delete {media_count} media messages for app {old_db_id}")
                        for i in range(1, media_count + 1):
                            try:
                                target_id = int(old_msg_id) - i
                                bot_client.delete_message(cid, target_id)
                                print(f"   Deleted media msg {target_id}")
                            except Exception: pass
                    except Exception as tg_del_e:
                        print(f"   TG Delete Err: {tg_del_e}")

                supabase_client.table("casting_applications").delete().eq("id", old_db_id).execute()
                print(f"✅ Deduplicated: Deleted old application {old_db_id}")
    except Exception as dedup_e:
        print(f"Deduplication Error: {dedup_e}")

def _auto_register_contact(data, cid, tid, supabase_client):
    try:
        name, phone = data.get('full_name'), data.get('phone')
        if name and phone:
            supabase_client.table("contacts").upsert({
                "name": name, "phone": phone, "thread_id": tid, "chat_id": cid, "category": "casting"
            }, on_conflict="phone,chat_id,thread_id").execute()
    except: pass

def _prepare_telegram_media(data, simple_caption, types_module):
    photos = data.get('photo_urls', [])
    video = data.get('video_audition_url')
    media = []
    for i, url in enumerate(photos):
        if i == 0: media.append(types_module.InputMediaPhoto(url, caption=simple_caption, parse_mode="HTML"))
        else: media.append(types_module.InputMediaPhoto(url))
    if video:
        if not media: media.append(types_module.InputMediaVideo(video, caption=simple_caption, parse_mode="HTML"))
        else: media.append(types_module.InputMediaVideo(video))
    return media

def _get_app_id_and_selection_state(data, phone, target, supabase_client):
    app_id = data.get('application_id') or data.get('id')
    is_selected = False
    if not app_id:
        try:
            app_res = supabase_client.table("casting_applications").select("id, is_selected").eq("phone", phone).eq("casting_target", target).order("created_at", descending=True).limit(1).execute()
            if app_res.data:
                app_id = app_res.data[0]['id']
                is_selected = app_res.data[0].get('is_selected', False)
        except: pass
    else:
        try:
            sel_res = supabase_client.table("casting_applications").select("is_selected").eq("id", app_id).single().execute()
            is_selected = sel_res.data.get('is_selected', False) if sel_res.data else False
        except: pass
    return app_id, is_selected

"""

# Insert helpers right before the notify_casting function
content = content.replace("@app.route('/api/casting', methods=['POST', 'OPTIONS'])\ndef notify_casting():", helper_funcs + "\n@app.route('/api/casting', methods=['POST', 'OPTIONS'])\ndef notify_casting():")

# Step 1: Replace Blacklist Check
bl_regex = r"# --- 0\. BLACKLIST CHECK ---.*?(?=# Cast to integers)"
bl_replace = """# --- 0. BLACKLIST CHECK ---
        is_blocked, bl_response = _check_blacklist(phone, insta, supabase)
        if is_blocked:
            return jsonify(bl_response), 200

        """
content = re.sub(bl_regex, bl_replace, content, flags=re.DOTALL)

# Step 2: Replace Self Cleanup
sc_regex = r"# 0\. SELF-CLEANUP:.*?(?=# 1\. FIND AND DELETE DUPLICATES)"
sc_replace = """# 0. SELF-CLEANUP: If this is an UPDATE to an existing application, delete its previous message FIRST.
        app_id = data.get('application_id')
        _cleanup_previous_application(app_id, cid, supabase, bot)

        """
content = re.sub(sc_regex, sc_replace, content, flags=re.DOTALL)

# Step 3: Replace Find & Delete Duplicates
dup_regex = r"# 1\. FIND AND DELETE DUPLICATES.*?(?=# 2\. Auto-Register Contact)"
dup_replace = """# 1. FIND AND DELETE DUPLICATES (Strictly Different IDs)
        _remove_duplicate_applications(data, cid, tid, phone, insta, app_id, supabase, bot)

        """
content = re.sub(dup_regex, dup_replace, content, flags=re.DOTALL)

# Step 4: Replace Auto Register Contact
ar_regex = r"# 2\. Auto-Register Contact.*?except: pass\n"
ar_replace = """# 2. Auto-Register Contact
        _auto_register_contact(data, cid, tid, supabase)
"""
content = re.sub(ar_regex, ar_replace, content, flags=re.DOTALL)

# Step 5: Replace Media Prep
med_regex = r"        photos = data\.get\('photo_urls', \[\]\).*?media\.append\(types\.InputMediaVideo\(video\)\)\n"
med_replace = """        media = _prepare_telegram_media(data, simple_caption, types)\n"""
content = re.sub(med_regex, med_replace, content, flags=re.DOTALL)

# Step 6: Replace App ID and selection state fetching
app_regex = r"        app_id = data\.get\('application_id'\) or data\.get\('id'\) # CHECK 'id' field too!.*?(?=        if app_id:)"
app_replace = """        app_id, is_selected = _get_app_id_and_selection_state(data, phone, target, supabase)

"""
content = re.sub(app_regex, app_replace, content, flags=re.DOTALL)

with open('api/index.py', 'w') as f:
    f.write(content)
