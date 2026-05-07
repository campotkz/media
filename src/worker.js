export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Обработка CORS
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    const tD = ["api", "telegram", "org"].join(".");
    const sD = ["waekzofajzqcpoeldhkt", "supabase", "co"].join(".");
    const supabaseUrl = env.SUPABASE_URL || `https://${sD}`;
    const supabaseKey = env.SUPABASE_ANON_KEY;
    const botToken = env.BOT_TOKEN;

    // Вспомогательная функция для ответов
    const jsonRes = (data, status = 200) => new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
    });

    // --- SETUP WEBHOOK (Временный эндпоинт по запросу пользователя) ---
    if (url.pathname === "/api/setup-webhook" && botToken) {
      const workerUrl = `https://${url.hostname}`;
      const res = await fetch(`https://${tD}/bot${botToken}/setWebhook?url=${workerUrl}`);
      const result = await res.json();
      return jsonRes({ status: "webhook_setup", result });
    }

    // GET /api/check-phone - Фоновая проверка телефона
    if (request.method === "GET" && url.pathname === "/api/check-phone") {
      const phone = url.searchParams.get("phone");
      const project = url.searchParams.get("project");
      if (!phone) return jsonRes({ error: "No phone" }, 400);

      const res = await fetch(`${supabaseUrl}/rest/v1/casting_applications?phone=eq.${encodeURIComponent(phone)}`, {
        headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
      });
      const existing = await res.json();

      if (existing.length > 0) {
        const user = existing[0];
        if (user.is_blocked) return jsonRes({ status: "blocked" });
        
        // Проверяем, подавался ли уже на этот проект
        const sameProject = existing.find(a => a.project_name === project);
        if (sameProject) return jsonRes({ status: "already_applied", project: project });
        
        return jsonRes({ status: "exists_other_project", projects: existing.map(a => a.project_name) });
      }
      return jsonRes({ status: "new" });
    }

    // GET /api/projects - Список уникальных проектов
    if (request.method === "GET" && url.pathname === "/api/projects") {
      try {
        const res = await fetch(`${supabaseUrl}/rest/v1/casting_applications?select=project_name`, {
          headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
        });
        const data = await res.json();
        const projects = [...new Set(data.map(d => d.project_name))]
          .filter(p => p && p !== "General" && p !== "Тестовый" && p !== "Test");
        return jsonRes(projects);
      } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    // GET /api/applications - API для дашборда с фильтрами
    if (request.method === "GET" && url.pathname === "/api/applications") {
      const p = url.searchParams;
      let query = `${supabaseUrl}/rest/v1/casting_applications?select=*&order=created_at.desc`;
      
      const project = p.get('project');
      const city = p.get('city');
      const gender = p.get('gender');
      const ageMin = p.get('age_min');
      const ageMax = p.get('age_max');
      const search = p.get('search');
      const approved = p.get('approved');
      const status = p.get('status');

      if (project && project !== 'Все') query += `&project_name=eq.${encodeURIComponent(project)}`;
      if (city && city !== 'Все') query += `&city=eq.${encodeURIComponent(city)}`;
      if (gender && gender !== 'Все') query += `&gender=eq.${encodeURIComponent(gender)}`;
      if (ageMin) query += `&age_num=gte.${ageMin}`;
      if (ageMax) query += `&age_num=lte.${ageMax}`;
      if (search) query += `&full_name=ilike.*${encodeURIComponent(search)}*`;
      if (status) query += `&status=eq.${status}`;
      if (approved === 'true') query += `&status=eq.approved`;
      
      try {
          const res = await fetch(query, { headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` } });
          const data = await res.json();
          return jsonRes(data);
      } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    // PATCH /api/applications/update - Модерация (рейтинг 1-10, статус, заметки)
    if (request.method === "PATCH" && url.pathname === "/api/applications/update") {
      try {
        const body = await request.json();
        const { id, ...updates } = body;
        if (!id) return jsonRes({ error: "No ID" }, 400);

        const res = await fetch(`${supabaseUrl}/rest/v1/casting_applications?id=eq.${id}`, {
          method: 'PATCH',
          headers: { 
            'Content-Type': 'application/json', 
            'apikey': supabaseKey, 
            'Authorization': `Bearer ${supabaseKey}`,
            'Prefer': 'return=representation'
          },
          body: JSON.stringify({ ...updates, updated_at: new Date().toISOString() })
        });
        const updated = await res.json();
        return jsonRes({ status: "ok", data: updated });
      } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    // GET /api/applications/by-token - Получение анкеты по токену доп. инфо
    if (request.method === "GET" && url.pathname === "/api/applications/by-token") {
       const token = url.searchParams.get("token");
       if (!token) return jsonRes({ error: "No token" }, 400);
       try {
          const res = await fetch(`${supabaseUrl}/rest/v1/casting_applications?extra_info_token=eq.${token}`, {
            headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
          });
          const data = await res.json();
          if (data.length === 0) return jsonRes({ error: "Not found" }, 404);
          return jsonRes(data[0]);
       } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    // PUT /api/applications/additional - Дозагрузка данных актером (режим дозапроса)
    if (request.method === "PUT" && url.pathname === "/api/applications/additional") {
      try {
        const body = await request.json();
        const { token, ...updates } = body;
        if (!token) return jsonRes({ error: "No token" }, 400);

        // 1. Находим анкету
        const findRes = await fetch(`${supabaseUrl}/rest/v1/casting_applications?extra_info_token=eq.${token}`, {
            headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
        });
        const existing = await findRes.json();
        if (existing.length === 0) return jsonRes({ error: "Invalid token" }, 404);
        
        const appId = existing[0].id;

        // 2. Обновляем (приклеиваем данные)
        const patchRes = await fetch(`${supabaseUrl}/rest/v1/casting_applications?id=eq.${appId}`, {
          method: 'PATCH',
          headers: { 
            'Content-Type': 'application/json', 
            'apikey': supabaseKey, 
            'Authorization': `Bearer ${supabaseKey}`
          },
          body: JSON.stringify({ 
            ...updates, 
            extra_info_requested: false, // Сбрасываем флаг, так как данные получены
            updated_at: new Date().toISOString() 
          })
        });
        
        return jsonRes({ status: "ok" });
      } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    // POST /api/applications/request-info - Генерация токена для доп. инфо
    if (request.method === "POST" && url.pathname === "/api/applications/request-info") {
       try {
          const { id } = await request.json();
          const token = crypto.randomUUID();
          await fetch(`${supabaseUrl}/rest/v1/casting_applications?id=eq.${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` },
            body: JSON.stringify({ extra_info_token: token, extra_info_requested: true })
          });
          return jsonRes({ token });
       } catch (err) { return jsonRes({ error: err.message }, 500); }
    }

    if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

    const contentType = request.headers.get("content-type") || "";

    // Обработка Telegram Webhook
    if (request.method === "POST" && contentType.includes("application/json")) {
      try {
        const update = await request.json();
        const message = update.message || update.callback_query?.message;
        if (!message) return new Response("OK", { status: 200 });

        const chatId = message.chat.id;
        const fromId = update.message?.from?.id || update.callback_query?.from?.id;
        const msgText = update.message?.text || "";

        const allowedEnv = (env.ALLOWED_CHATS || "-8534227633,-195051697,542053490,-1003738942785").split(",").map(id => id.trim());
        async function checkAccess() {
          if (allowedEnv.includes(String(chatId))) return true;
          try {
            const res = await fetch(`${supabaseUrl}/rest/v1/allowed_chats?chat_id=eq.${chatId}`, {
              headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
            });
            const data = await res.json();
            return data && data.length > 0;
          } catch (e) { return false; }
        }

        const hasAccess = (fromId === 542053490) || await checkAccess();
        if (!hasAccess) {
          if (msgText.startsWith("/")) {
            await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: `🚫 <b>Доступ запрещен.</b>\nЭтот бот настроен только для работы в закрытых группах GULYWOOD.\n\nID этого чата: <code>${chatId}</code>\n<i>Передайте этот ID администратору для добавления в белый список.</i>`,
                parse_mode: "HTML"
              })
            });
          }
          return new Response("OK", { status: 200 });
        }

        // 2. Команды Админа (542053490)
        if (fromId === 542053490) {
          if (msgText.startsWith("/white")) {
            const parts = msgText.split(" ");
            if (parts.length < 2) {
              await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  chat_id: chatId,
                  text: "Пришли мне ID нового чата. Чтобы узнать его, перешли любое сообщение из нужной группы в бот @getidsbot.\n\nИспользование: <code>/white -100123456789</code>",
                  parse_mode: "HTML"
                })
              });
            } else {
              const newId = parts[1];
              await fetch(`${supabaseUrl}/rest/v1/allowed_chats`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` },
                body: JSON.stringify({ chat_id: newId, added_by: fromId })
              });
              await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: chatId, text: `✅ Чат ${newId} добавлен в белый список.` })
              });
            }
            return new Response("OK", { status: 200 });
          }

          if (msgText.startsWith("/black")) {
            const parts = msgText.split(" ");
            if (parts.length < 2) {
              await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: chatId, text: "Использование: <code>/black -100123456789</code>", parse_mode: "HTML" })
              });
            } else {
              const targetId = parts[1];
              await fetch(`${supabaseUrl}/rest/v1/allowed_chats?chat_id=eq.${targetId}`, {
                method: 'DELETE',
                headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
              });
              await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: chatId, text: `❌ Чат ${targetId} удален из белого списка.` })
              });
            }
            return new Response("OK", { status: 200 });
          }

          if (msgText.startsWith("/deleteall")) {
            await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: "⚠️ <b>ВНИМАНИЕ!</b>\nВы собираетесь удалить ВСЕ данные кастинга из базы. Для подтверждения введите: <code>/confirm_delete_all</code>",
                parse_mode: "HTML"
              })
            });
            return new Response("OK", { status: 200 });
          }

          if (msgText.startsWith("/confirm_delete_all")) {
            await fetch(`${supabaseUrl}/rest/v1/casting_applications`, {
              method: 'DELETE',
              headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
            });
            await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ chat_id: chatId, text: "🧨 База данных кастинга полностью очищена." })
            });
            return new Response("OK", { status: 200 });
          }
        }

        // 3. Обычные команды
        if (msgText === "/hub" || msgText === "/start") {
          const dashboardUrl = "https://campotkz.github.io/media/casting_dashboard.html";
          await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: `🚀 <b>Casting Hub</b>\n\nЗдесь вы можете просматривать анкеты и информацию об актерах:\n\n🔗 <a href="${dashboardUrl}">Открыть Дашборд</a>`,
              parse_mode: "HTML"
            })
          });
        }
        
        return new Response("OK", { status: 200 });
      } catch (e) { return new Response("OK", { status: 200 }); }
    }

    // --- ОБРАБОТКА ФОРМЫ (АНКЕТЫ) ---
    try {
      const formData = await request.formData();
      const isUpdate = formData.get("update") === "true";
      const chatId = env.CHAT_ID || "-1003893557217";

      const data = {};
      formData.forEach((value, key) => { if (typeof value === "string") data[key] = value; });

      const phone = data.phone;
      const targetProject = data.casting_target || "General Casting";
      const explicitId = data.app_id;

      let userRecord = null;
      if (explicitId) {
        const res = await fetch(`${supabaseUrl}/rest/v1/casting_applications?id=eq.${explicitId}`, {
          headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
        });
        const recs = await res.json();
        userRecord = recs[0];
      }

      if (!userRecord && phone) {
        // 1. Проверка дубликатов перед сохранением
        const checkRes = await fetch(`${supabaseUrl}/rest/v1/casting_applications?phone=eq.${encodeURIComponent(phone)}&project_name=eq.${encodeURIComponent(targetProject)}`, {
          headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
        });
        const existing = await checkRes.json();
        userRecord = existing[0];
        
        if (userRecord && !isUpdate) {
          return jsonRes({ status: "error", code: "already_applied", message: "Вы уже подавали заявку на этот проект." }, 400);
        }
      }
      
      if (userRecord && userRecord.is_blocked) {
        return jsonRes({ status: "error", code: "blocked", message: "Ваш аккаунт заблокирован системой модерации." }, 403);
      }

      const videoFile = formData.get("video");
      const threadId = data.thread_id ? parseInt(data.thread_id) : null;
      const targetChatId = chatId; // Forcing env.CHAT_ID for security as per requirements

      const headerText = isUpdate ? `🔄 <b>ОБНОВЛЕННАЯ АНКЕТА: ${data.full_name || "—"}</b>` : `🌟 <b>НОВАЯ АНКЕТА: ${data.full_name || "—"}</b>`;

      const text = `
${headerText}
🎯 Проект: <b>${targetProject}</b>
🎭 Персонаж: <b>${data.character_name || "—"}</b>
━━━━━━━━━━━━━━━━━━━━

👤 <b>Данные:</b> ${data.city || "—"} | ${data.gender || "—"}
🎂 Возраст: ${data.dob || "—"}
📏 Рост/Вес: ${data.height_weight || "—"}
📱 Тел: ${data.phone || "—"}
🔗 Inst: ${data.instagram || "—"}

🎭 <b>Опыт:</b>
${data.experience || "—"}

💰 Бюджет: ${data.fee_range || "—"}
      `.trim();

      const msgRes = await fetch(`https://${tD}/bot${botToken}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: targetChatId,
          text: text,
          parse_mode: "HTML",
          message_thread_id: threadId
        })
      });

      const msgResult = await msgRes.json();
      if (!msgResult.ok) throw new Error(`TG Error: ${msgResult.description}`);
      const messageId = msgResult.result.message_id;

      // Фото и Видео (аналогично предыдущей версии)
      const photos = formData.getAll("photos");
      if (photos.length > 0) {
        const mediaFormData = new FormData();
        mediaFormData.append("chat_id", targetChatId);
        mediaFormData.append("reply_to_message_id", messageId);
        if (threadId) mediaFormData.append("message_thread_id", threadId);
        const media = [];
        photos.slice(0, 10).forEach((photo, index) => {
          const fid = `p${index}`;
          media.push({ type: "photo", media: `attach://${fid}` });
          mediaFormData.append(fid, photo);
        });
        mediaFormData.append("media", JSON.stringify(media));
        await fetch(`https://${tD}/bot${botToken}/sendMediaGroup`, { method: "POST", body: mediaFormData });
      }

      if (videoFile && videoFile.size > 0) {
        const vData = new FormData();
        vData.append("chat_id", targetChatId);
        vData.append("video", videoFile);
        vData.append("reply_to_message_id", messageId);
        if (threadId) vData.append("message_thread_id", threadId);
        await fetch(`https://${tD}/bot${botToken}/sendVideo`, { method: "POST", body: vData });
      }

      // Сохранение/Обновление в Supabase
      let videoTgLink = null;
      if (videoFile && videoFile.size > 0) {
         const cleanChatId = String(targetChatId).replace('-100', '');
         videoTgLink = `https://t.me/c/${cleanChatId}/${messageId}`;
      }
      const expText = data.experience || '';
      const summary = `${data.dob || '?'} лет, ${data.height_weight || '?'}. Опыт: ${expText.substring(0, 50)}...`;
      
      // Populate numeric fields for filtering
      const ageNum = parseInt(data.dob) || null;
      const heightNum = parseInt(data.height) || null;
      const weightNum = parseInt(data.weight) || null;
      const gender = data.gender || null;
      
      const payload = {
          full_name: data.full_name || '',
          age: data.dob || '',
          age_num: ageNum,
          height_num: heightNum,
          weight_num: weightNum,
          gender: gender,
          height_weight: data.height_weight || '',
          city: data.city || '',
          phone: data.phone || '',
          instagram: data.instagram || '',
          project_name: targetProject,
          character_name: data.character_name || '',
          experience_summary: summary,
          video_tg_link: videoTgLink,
          updated_at: new Date().toISOString()
      };

      if (isUpdate && userRecord) {
        // UPDATE
        await fetch(`${supabaseUrl}/rest/v1/casting_applications?id=eq.${userRecord.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` },
            body: JSON.stringify(payload)
        });
      } else {
        // INSERT
        await fetch(`${supabaseUrl}/rest/v1/casting_applications`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}`, 'Prefer': 'return=minimal' },
            body: JSON.stringify({ ...payload, id: crypto.randomUUID(), created_at: new Date().toISOString() })
        });
      }

      return jsonRes({ status: "ok", message_id: messageId });

    } catch (err) {
      return jsonRes({ status: "error", error: err.message }, 500);
    }
  }
};
