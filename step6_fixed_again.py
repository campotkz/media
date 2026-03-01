import re

with open('api/index.py', 'r') as f:
    content = f.read()

helper = """
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

content = content.replace("@app.route('/api/casting', methods=['POST', 'OPTIONS'])\ndef notify_casting():", helper + "\n@app.route('/api/casting', methods=['POST', 'OPTIONS'])\ndef notify_casting():")

med_regex = r"        photos = data\.get\('photo_urls', \[\]\)\n        video = data\.get\('video_audition_url'\)\n\n        media = \[\]\n        for i, url in enumerate\(photos\):\n            if i == 0:\n                media\.append\(types\.InputMediaPhoto\(url, caption=simple_caption, parse_mode=\"HTML\"\)\)\n            else:\n                media\.append\(types\.InputMediaPhoto\(url\)\)\n        \n        if video:\n            if not media:\n                media\.append\(types\.InputMediaVideo\(video, caption=simple_caption, parse_mode=\"HTML\"\)\)\n            else:\n                media\.append\(types\.InputMediaVideo\(video\)\)"
med_replace = """        media = _prepare_telegram_media(data, simple_caption, types)"""
content = re.sub(med_regex, med_replace, content, flags=re.DOTALL)

app_regex = r"        app_id = data\.get\('application_id'\) or data\.get\('id'\) # CHECK 'id' field too!.*?(?=        if app_id:)"
app_replace = """        app_id, is_selected = _get_app_id_and_selection_state(data, phone, target, supabase)

"""
content = re.sub(app_regex, app_replace, content, flags=re.DOTALL)

with open('api/index.py', 'w') as f:
    f.write(content)
