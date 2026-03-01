    function render() {
      const grid = document.getElementById("grid");
      grid.innerHTML = "";
      const today = new Date();

      document.getElementById("monthLabel").textContent = monthName(currentMonth);
      document.getElementById("selectedLabel").textContent = `${niceDate(selectedDate)} (${weekday(selectedDate)})`;

      const monEvents = allEvents.filter(e => {
        const d = new Date(e.date);

        // Filter by ACTIVE projects
        const proj = clientsData.find(c => c.name === e.project);
        if (proj && !proj.is_active) return false;

        return d.getFullYear() === currentMonth.getFullYear() && d.getMonth() === currentMonth.getMonth();
      });

      // Calculate Stats
      const done = monEvents.filter(e => e.status === 'done').length;
      const pending = monEvents.filter(e => e.status === 'pending').length;
      const overdue = monEvents.filter(e => e.status === 'overdue').length;

      // Update Header with Icons
      const statHtml = `
        <span style="color:#4cd964">✅ ${done}</span>
        <span style="color:#ffcc00; margin-left:8px">🟡 ${pending}</span>
        <span style="color:#ff3b30; margin-left:8px">🔥 ${overdue}</span>
      `;
      document.getElementById("monthStat").innerHTML = statHtml;

      const first = startMonth(currentMonth);
      const offset = (first.getDay() + 6) % 7;
      const start = new Date(first);
      start.setDate(first.getDate() - offset);

      for (let i = 0; i < 42; i++) {
        const d = new Date(start);
        d.setDate(start.getDate() + i);
        const iso = toISO(d);

        // Dot Logic (Shoots)
        const dayEvents = allEvents.filter(e => e.date === iso);
        let dotsHtml = "";
        dayEvents.forEach(e => {
          const st = getStatus(e);
          dotsHtml += `<div class="dot ${st}"></div>`;
        });

        // Line Logic (Tasks)
        const dayTasks = allTasks.filter(t => {
          if (t.status === 'done') return false;
          if (!t.deadline) return false;

          // Hide tasks for INACTIVE projects
          const p = clientsData.find(c => c.name === t.project_id);
          const cp = clientsData.find(c => c.name === t.casting_project);
          if (p && !p.is_active) return false;
          if (cp && !cp.is_active) return false;

          // Startdate: created_at or fallback to deadline if missing
          // We want to show line from start to deadline
          // If created_at is missing, we assume it's a single day task (deadline)
          let start = t.created_at ? t.created_at.split('T')[0] : t.deadline;
          if (start > t.deadline) start = t.deadline; // Safety

          return iso >= start && iso <= t.deadline;
        });

        let linesHtml = "";
        if (dayTasks.length > 0) {
          linesHtml += `<div class="task-lines">`;
          dayTasks.forEach(t => {
            const start = t.created_at ? t.created_at.split('T')[0] : t.deadline;
            const isStart = (start === iso);
            const isEnd = (t.deadline === iso);

            // Style for rounded ends
            let style = '';

            // GRADIENT COLOR CALCULATION
            const startDate = new Date(start);
            const endDate = new Date(t.deadline);
            const currDate = new Date(iso);

            // Total duration in ms
            const total = endDate - startDate;
            // Elapsed in ms
            const elapsed = currDate - startDate;

            // Ratio (0 to 1)
            let ratio = 0;
            if (total > 0) ratio = Math.max(0, Math.min(1, elapsed / total));

            // Interpolate color from #FFCC00 (Yellow) to #FF3B30 (Red)
            // Yellow: 255, 204, 0
            // Red:    255, 59,  48
            const r = Math.round(255 + ratio * (255 - 255));
            const g = Math.round(204 + ratio * (59 - 204));
            const b = Math.round(0 + ratio * (48 - 0));
            const color = `rgb(${r}, ${g}, ${b})`;

            // Apply styles
            if (isStart && isEnd) { style = 'border-radius: 2px; margin: 0 2px;'; }
            else if (isStart) { style = 'border-radius: 2px 0 0 2px; margin-right:-4px;'; }
            else if (isEnd) { style = 'border-radius: 0 2px 2px 0; margin-left:-4px;'; }
            else { style = 'border-radius: 0; margin: 0 -4px;'; }

            const stClass = (t.deadline < todayISO) ? 'overdue' : 'pending';

            // Override background color if pending/overdue (completed is green usually, but let's stick to gradient for active)
            if (t.status !== 'done') {
              style += ` background-color: ${color} !important;`;
            }

            linesHtml += `<div class="task-line ${stClass}" style="${style}"></div>`;
          });
          linesHtml += `</div>`;
        }

        // Highlight Logic
        const isPast = iso < todayISO;
        const hasPendingShoot = dayEvents.some(e => getStatus(e) === 'pending');

        const cell = document.createElement("div");
        let cellClasses = "day" + (d.getMonth() !== currentMonth.getMonth() ? " out" : "") + (iso === toISO(selectedDate) ? " sel" : "") + (iso === toISO(today) ? " today" : "");
        if (hasPendingShoot) cellClasses += " has-pending";

        cell.className = cellClasses;

        // Gray out past days numbers
        const numStyle = isPast ? 'style="color:#444;"' : '';

        cell.innerHTML = `<div class="num" ${numStyle}><span>${d.getDate()}</span></div><div class="dots">${dotsHtml}</div>${linesHtml}`;
        cell.onclick = () => {
          selectedDate = d;
          selectedId = null;
          selectedTaskId = null; // Clear Task editing state too
          toggleForm(false);
          document.getElementById('taskForm').style.display = 'none';
          render();
        };
        grid.appendChild(cell);
      }

      // Список проектов дня (Shoots + Tasks)
      const listDiv = document.getElementById("eventList");
      const dayShoots = allEvents.filter(e => {
        const proj = clientsData.find(c => c.name === e.project);
        if (proj && !proj.is_active) return false;
        return e.date === toISO(selectedDate);
      }).sort((a, b) => a.callTime.localeCompare(b.callTime));

      const dayTasksList = allTasks.filter(t => {
        const p = clientsData.find(c => c.name === t.project_id);
        const cp = clientsData.find(c => c.name === t.casting_project);
        if (p && !p.is_active) return false;
        if (cp && !cp.is_active) return false;
        return t.deadline === toISO(selectedDate);
      });

      let html = "";
      if (!dayShoots.length && !dayTasksList.length) html = '<div class="item" style="color:gray">Нет событий</div>';

      // Render Shoots
      dayShoots.forEach(e => {
        const st = getStatus(e);
        // ... (Buttons logic same as before)
        let buttons = "";
        if (st === 'pending' || st === 'overdue') buttons += `<button class="icon-btn done-btn" onclick="event.stopPropagation(); toggleStatus('${e.id}', 'done')">✅</button>`;
        if (st === 'done') buttons += `<button class="icon-btn" onclick="event.stopPropagation(); toggleStatus('${e.id}', 'pending')">↩️</button>`;
        if (st === 'overdue') buttons += `<button class="icon-btn resched-btn" onclick="event.stopPropagation(); rescheduleTask('${e.id}')">📅</button>`;

        html += `
            <div class="item ${st}" onclick="editShoot('${e.id}')">
                <div class="item-content">
                    <b>${e.project || "Без названия"}</b><br>
                    <small>🎥 ${e.callTime || "--:--"}—${e.wrapTime || "--:--"} • ${e.location || ""}</small><br>
                    ${e.crew ? `<small style="opacity:0.7">👥 ${e.crew}</small><br>` : ''}
                    ${e.post_production ? `<small style="color:var(--accent)">✂️ ${e.post_production}</small>` : ''}
                </div>
                <div class="item-actions">${buttons}</div>
            </div>
        `;
      });

      // Render Tasks
      dayTasksList.forEach(t => {
        const st = t.status === 'done' ? 'done' : (t.deadline < todayISO ? 'overdue' : 'pending');
        // Task Buttons
        let buttons = "";
        if (t.status !== 'done') buttons += `<button class="icon-btn done-btn" onclick="event.stopPropagation(); toggleTaskStatus('${t.id}', 'done')">✅</button>`;
        else buttons += `<button class="icon-btn" onclick="event.stopPropagation(); toggleTaskStatus('${t.id}', 'pending')">↩️</button>`;
        buttons += `<button class="icon-btn resched-btn" onclick="event.stopPropagation(); deleteTask('${t.id}')">🗑</button>`;

        html += `
            <div class="item ${st}" style="border-left: 2px solid ${st === 'done' ? '#4cd964' : '#ffcc00'};" onclick="editTask('${t.id}')">
                <div class="item-content">
                    <b>${t.title}</b><br>
                    <small>📌 ${t.project ? t.project + ' • ' : ''}${t.type}</small>
                </div>
                <div class="item-actions">${buttons}</div>
            </div>
         `;
      });

      listDiv.innerHTML = html;
