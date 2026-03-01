    function exportShootToExcel(event) {
      const e = {
        project: document.getElementById("project").value,
        location: document.getElementById("location").value,
        date: document.getElementById("selectedLabel").textContent,
        callTime: document.getElementById("callTime").value,
        wrapTime: document.getElementById("wrapTime").value,
        address: document.getElementById("address").value,
        contact: document.getElementById("contact").value,
        deliverables: document.getElementById("deliverables").value,
        notes: document.getElementById("notes").value,
        crew: document.getElementById("crew").value,
        actors: document.getElementById("actors").value,
      };

      const timing = [];
      document.querySelectorAll("#timingRows .timing-row").forEach(row => {
        timing.push({
          START: row.querySelector(".t-start").value,
          END: row.querySelector(".t-end").value,
          LOC: row.querySelector(".t-loc").value,
          TASK: row.querySelector(".t-task").value,
          ACTORS: row.querySelector(".t-act").value,
          NOTES: row.querySelector(".t-notes").value,
          LINK: row.querySelector(".t-link") ? row.querySelector(".t-link").value : ''
        });
      });

      const gear = [];
      document.querySelectorAll("#gearRows .gear-row").forEach(row => {
        gear.push({
          CAT: row.querySelector(".g-cat").value,
          MODEL: row.querySelector(".g-model").value,
          QTY: row.querySelector(".g-qty").value,
          NOTES: row.querySelector(".g-note").value
        });
      });

      const wb = XLSX.utils.book_new();

      // --- Helper: add borders + col widths to a sheet ---
      function formatSheet(ws, colWidths) {
        const range = XLSX.utils.decode_range(ws['!ref'] || 'A1');
        const border = {
          top: { style: 'thin', color: { rgb: '999999' } },
          bottom: { style: 'thin', color: { rgb: '999999' } },
          left: { style: 'thin', color: { rgb: '999999' } },
          right: { style: 'thin', color: { rgb: '999999' } }
        };
        for (let R = range.s.r; R <= range.e.r; R++) {
          for (let C = range.s.c; C <= range.e.c; C++) {
            const addr = XLSX.utils.encode_cell({ r: R, c: C });
            if (!ws[addr]) ws[addr] = { v: '', t: 's' };
            if (!ws[addr].s) ws[addr].s = {};
            ws[addr].s.border = border;
            // Bold header row
            if (R === 0) {
              ws[addr].s.font = { bold: true, sz: 12 };
              ws[addr].s.fill = { fgColor: { rgb: 'E8E8E8' } };
            }
            ws[addr].s.alignment = { vertical: 'center', wrapText: true };
          }
        }
        if (colWidths) ws['!cols'] = colWidths.map(w => ({ wch: w }));
      }

      // ИНФО sheet
      const infoData = [
        ["ПОЛЕ", "ЗНАЧЕНИЕ"],
        ["ПРОЕКТ", e.project], ["ДАТА", e.date], ["ЛОКАЦИЯ", e.location],
        ["АДРЕС", e.address], ["КОНТАКТ", e.contact], ["CALL", e.callTime], ["WRAP", e.wrapTime],
        [""], ["ТЗ", e.deliverables], ["ПРИМЕЧАНИЯ", e.notes], ["КОМАНДА", e.crew], ["АКТЕРЫ", e.actors]
      ];
      const wsInfo = XLSX.utils.aoa_to_sheet(infoData);
      formatSheet(wsInfo, [16, 50]);
      XLSX.utils.book_append_sheet(wb, wsInfo, "ИНФО");

      // ТАЙМИНГ sheet
      if (timing.length) {
        const wsTiming = XLSX.utils.json_to_sheet(timing);
        formatSheet(wsTiming, [10, 10, 18, 22, 18, 22, 30]);
        XLSX.utils.book_append_sheet(wb, wsTiming, "ТАЙМИНГ");
      }

      // ТЕХНИКА sheet
      if (gear.length) {
        const wsGear = XLSX.utils.json_to_sheet(gear);
        formatSheet(wsGear, [14, 30, 8, 25]);
        XLSX.utils.book_append_sheet(wb, wsGear, "ТЕХНИКА");
      }

      const fileName = `Shoot_${e.project.replace(/\s+/g, '_')}_${e.date.replace(/[^\d.]/g, '')}.xlsx`;

      // 1. Try local download (might be blocked in TG browser)
      try { XLSX.writeFile(wb, fileName); } catch (ex) { console.warn("Local DL failed", ex); }

      // 2. Telegram Send (Reliable)
      const base64Data = XLSX.write(wb, { type: 'base64', bookType: 'xlsx' });
      const exportBtn = (event && event.target) ? (event.target.tagName === 'BUTTON' ? event.target : event.target.closest('button')) : null;

      if (exportBtn) {
        exportBtn.disabled = true;
        exportBtn.innerHTML = "⌛...";
      }

      fetch('https://media-seven-eta.vercel.app/api/send_excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: e.project,
          filename: fileName,
          base64_data: base64Data
        })
      })
        .then(res => res.json())
        .then(res => {
          if (res.status === 'ok') {
            if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
            if (exportBtn) {
              exportBtn.innerHTML = "✅ В ТГ";
              setTimeout(() => { exportBtn.innerHTML = "📊 Excel"; exportBtn.disabled = false; }, 2000);
            }
          } else {
            alert("Ошибка TG: " + res.error);
            if (exportBtn) { exportBtn.innerHTML = "❌"; exportBtn.disabled = false; }
          }
        })
        .catch(err => {
          console.error("Fetch Error:", err);
          if (exportBtn) { exportBtn.innerHTML = "⚠️"; exportBtn.disabled = false; }
        });
    }

    function triggerExcelImport() { document.getElementById('excelFileInput').click(); }

    function openTimer() {
      const project = document.getElementById('project').value.trim() || 'Проект';

      // Try to get IDs from URL params (fallback if TG data is hidden)
      const urlParams = new URL(window.location.href).searchParams;
      const urlCid = urlParams.get('cid');
      const urlTid = urlParams.get('tid');

      // Get from Telegram initData
      const tgCid = tg?.initDataUnsafe?.chat?.id;
      const tgTid = tg?.initDataUnsafe?.chat?.thread_id;
