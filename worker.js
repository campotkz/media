export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Обработка CORS (для работы с фронтенда)
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    // GET /api/applications - API для дашборда
    if (request.method === "GET" && url.pathname === "/api/applications") {
      const supabaseUrl = env.SUPABASE_URL || "https://waekzofajzqcpoeldhkt.supabase.co";
      const supabaseKey = env.SUPABASE_ANON_KEY;
      
      if (!supabaseKey) {
          return new Response(JSON.stringify({ error: "Supabase keys not configured in worker" }), { status: 500, headers: { "Access-Control-Allow-Origin": "*" }});
      }

      const projectFilter = url.searchParams.get('project');
      const searchFilter = url.searchParams.get('search');
      
      let query = `${supabaseUrl}/rest/v1/casting_applications?select=*&order=created_at.desc`;
      if (projectFilter && projectFilter !== 'Все') {
          query += `&project_name=eq.${encodeURIComponent(projectFilter)}`;
      }
      if (searchFilter) {
          query += `&full_name=ilike.*${encodeURIComponent(searchFilter)}*`;
      }
      
      try {
          const res = await fetch(query, {
              headers: {
                  'apikey': supabaseKey,
                  'Authorization': `Bearer ${supabaseKey}`
              }
          });
          const data = await res.json();
          return new Response(JSON.stringify(data), {
              headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
          });
      } catch (err) {
          return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Access-Control-Allow-Origin": "*" }});
      }
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    try {
      const formData = await request.formData();
      const botToken = env.BOT_TOKEN;
      const chatId = env.CHAT_ID || "-1003893557217";

      // --- 1. Извлекаем текстовые поля ---
      const data = {};
      formData.forEach((value, key) => {
        if (typeof value === "string") {
          data[key] = value;
        }
      });

      // Извлекаем видеофайл
      const videoFile = formData.get("video");

      // --- 2. Маршрутизация по топикам (Thread IDs) ---
      const topicMappings = {
        "General Casting": null,
        "Commercial Project X": 2,
        "Весы": 10,
        "Форт №307": 15
      };
      
      const target = data.casting_target || "General Casting";
      const threadId = data.thread_id ? parseInt(data.thread_id) : (topicMappings[target] || null);
      const targetChatId = data.chat_id || chatId;

      // --- 3. Формируем текст анкеты ---
      const text = `
🌟 <b>НОВАЯ АНКЕТА: ${data.full_name || "—"}</b>
🎯 Проект: <b>${target}</b>
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

      // --- 4. Шаг 1: Отправляем текст (sendMessage) ---
      const sendMsgUrl = `https://api.telegram.org/bot${botToken}/sendMessage`;
      const msgRes = await fetch(sendMsgUrl, {
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
      if (!msgResult.ok) {
        throw new Error(`Telegram SendMessage Error: ${msgResult.description}`);
      }

      const messageId = msgResult.result.message_id;

      // --- 5. Шаг 2: Отправляем фото (MediaGroup) ---
      const photos = formData.getAll("photos");
      if (photos.length > 0) {
        const sendMediaUrl = `https://api.telegram.org/bot${botToken}/sendMediaGroup`;
        const mediaFormData = new FormData();
        mediaFormData.append("chat_id", targetChatId);
        mediaFormData.append("reply_to_message_id", messageId);
        if (threadId) mediaFormData.append("message_thread_id", threadId);

        const media = [];
        photos.slice(0, 10).forEach((photo, index) => {
          const fileId = `photo_${index}`;
          media.push({
            type: "photo",
            media: `attach://${fileId}`
          });
          mediaFormData.append(fileId, photo);
        });

        mediaFormData.append("media", JSON.stringify(media));
        
        await fetch(sendMediaUrl, {
          method: "POST",
          body: mediaFormData
        });
      }

      // --- 6. Шаг 3: Отправляем видео (если есть) ---
      if (videoFile && videoFile.size > 0) {
        const sendVideoUrl = `https://api.telegram.org/bot${botToken}/sendVideo`;
        const videoData = new FormData();
        videoData.append("chat_id", targetChatId);
        videoData.append("video", videoFile);
        videoData.append("reply_to_message_id", messageId);
        if (threadId) videoData.append("message_thread_id", threadId);

        await fetch(sendVideoUrl, {
          method: "POST",
          body: videoData
        });
      }

      // --- 7. Шаг 4: Сохранение в Supabase ---
      const supabaseUrl = env.SUPABASE_URL || "https://waekzofajzqcpoeldhkt.supabase.co";
      const supabaseKey = env.SUPABASE_ANON_KEY;
      
      if (supabaseUrl && supabaseKey) {
        let videoTgLink = null;
        if (videoFile && videoFile.size > 0) {
           const cleanChatId = String(targetChatId).replace('-100', '');
           videoTgLink = `https://t.me/c/${cleanChatId}/${messageId}`;
        }
        
        const expText = data.experience || '';
        const shortExp = expText.length > 50 ? expText.substring(0, 50) + '...' : expText;
        const summary = `${data.dob || '?'} лет, ${data.height_weight || '?'}. Опыт: ${shortExp}`;

        const payload = {
            id: crypto.randomUUID(),
            full_name: data.full_name || '',
            age: data.dob || '',
            height_weight: data.height_weight || '',
            city: data.city || '',
            phone: data.phone || '',
            instagram: data.instagram || '',
            project_name: target,
            character_name: data.character_name || '',
            experience_summary: summary,
            photo_tg_ids: [], // TODO: map telegram file ids if needed
            video_tg_link: videoTgLink,
            created_at: new Date().toISOString()
        };

        await fetch(`${supabaseUrl}/rest/v1/casting_applications`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'apikey': supabaseKey,
                'Authorization': `Bearer ${supabaseKey}`,
                'Prefer': 'return=minimal'
            },
            body: JSON.stringify(payload)
        }).catch(err => console.error("Supabase Save Error:", err));
      }

      return new Response(JSON.stringify({ status: "ok", message_id: messageId }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });

    } catch (err) {
      return new Response(JSON.stringify({ status: "error", error: err.message }), {
        status: 500,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }
  }
};
