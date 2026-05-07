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

    // GET /api/applications - API для дашборда
    if (request.method === "GET" && url.pathname === "/api/applications") {
      const projectFilter = url.searchParams.get('project');
      const searchFilter = url.searchParams.get('search');
      let query = `${supabaseUrl}/rest/v1/casting_applications?select=*&order=created_at.desc`;
      if (projectFilter && projectFilter !== 'Все') query += `&project_name=eq.${encodeURIComponent(projectFilter)}`;
      if (searchFilter) query += `&full_name=ilike.*${encodeURIComponent(searchFilter)}*`;
      
      try {
          const res = await fetch(query, { headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` } });
          const data = await res.json();
          return jsonRes(data);
      } catch (err) {
          return jsonRes({ error: err.message }, 500);
      }
    }

    if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

    const contentType = request.headers.get("content-type") || "";

    // Обработка Telegram Webhook
    if (contentType.includes("application/json")) {
      try {
        const update = await request.json();
        if (update.message && update.message.text) {
          const msgText = update.message.text;
          const chatId = update.message.chat.id;
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

      // 1. Проверка дубликатов перед сохранением
      const checkRes = await fetch(`${supabaseUrl}/rest/v1/casting_applications?phone=eq.${encodeURIComponent(phone)}&project_name=eq.${encodeURIComponent(targetProject)}`, {
        headers: { 'apikey': supabaseKey, 'Authorization': `Bearer ${supabaseKey}` }
      });
      const existing = await checkRes.json();
      
      if (existing.length > 0 && !isUpdate) {
        return jsonRes({ status: "error", code: "already_applied", message: "Вы уже подавали заявку на этот проект." }, 400);
      }

      const userRecord = existing[0];
      if (userRecord && userRecord.is_blocked) {
        return jsonRes({ status: "error", code: "blocked", message: "Ваш аккаунт заблокирован системой модерации." }, 403);
      }

      const videoFile = formData.get("video");
      const threadId = data.thread_id ? parseInt(data.thread_id) : null;
      const targetChatId = data.chat_id || chatId;

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
      
      const payload = {
          full_name: data.full_name || '',
          age: data.dob || '',
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
