function renderStats(data) {
    const levels = data.priority_counts || {};
    const pending = currentEvents.filter(e => (e.status || 'pending') === 'pending').length;
    const recommended = currentEvents.filter(e => ['S', 'A'].includes(e.level || e.priority || 'B')).length;
    const todayCount = currentEvents.filter(e => eventDateKey(e) === todayChina()).length;
    setHTML('stats',
        statCard('stat-today', '今日活动', todayCount, '按时间线整理') +
        statCard('stat-pending', '待确认', pending, '等待你处理') +
        statCard('stat-recommend', '推荐活动', recommended || (levels.S || 0) + (levels.A || 0), 'S/A 优先级') +
        statCard('stat-favorite', '已收藏', data.favorite_count || 0, '长期保留')
    );
    renderSideRail(data);
}

function statCard(className, label, value, caption) {
    return html`<div class="stat ${className}"><div class="stat-top"><div class="k">${label}</div><span></span></div><div class="v">${value}</div><p>${caption}</p></div>`;
}

function renderTagOptions(tags) {
    const select = document.getElementById('tagFilter');
    const current = select.value;
    select.innerHTML = '<option value="">全部标签</option>' + tags.map(t => '<option value="' + esc(t) + '">' + esc(t) + '</option>').join('');
    select.value = current;
}

function openDayDetails(dateKey) {
    const items = currentEvents.filter(e => eventDateKey(e) === dateKey).sort((a, b) => {
        const levelOrder = { S: 0, A: 1, B: 2, C: 3 };
        const levelDiff = (levelOrder[a.level || a.priority || 'B'] ?? 2) - (levelOrder[b.level || b.priority || 'B'] ?? 2);
        if (levelDiff !== 0) return levelDiff;
        return String(a.title || '').localeCompare(String(b.title || ''));
    });
    window.EventRadarModals?.ensureModal('dayModal');
    document.getElementById('dayModalTitle').textContent = dateKey + ' 的活动';
    document.getElementById('dayModalBody').innerHTML = items.map(eventCard).join('') || '<div class="empty"><strong>这一天没有活动</strong></div>';
    openModal('dayModal');
}

function renderCalendar(events, range) {
    const root = document.getElementById('calendarRoot');
    const heads = ['一', '二', '三', '四', '五', '六', '日'].map(d => '<div class="weekday">周' + d + '</div>').join('');
    const byDate = {};
    events.forEach(e => {
        const key = eventDateKey(e);
        if (!key) return;
        byDate[key] = byDate[key] || [];
        byDate[key].push(e);
    });
    let dates = [];
    if (currentView === 'week') {
        for (let i = 0; i < 7; i++) {
            const d = new Date(range.startDate);
            d.setDate(range.startDate.getDate() + i);
            dates.push(d);
        }
    } else {
        const first = new Date(range.year, range.month, 1);
        const offset = (first.getDay() + 6) % 7;
        const start = new Date(first);
        start.setDate(first.getDate() - offset);
        for (let i = 0; i < 42; i++) {
            const d = new Date(start);
            d.setDate(start.getDate() + i);
            dates.push(d);
        }
    }
    let html = '<div class="calendar-grid ' + (currentView === 'week' ? 'week-grid' : '') + '">' + heads;
    dates.forEach(d => {
        const key = localDateKey(d);
        const out = currentView === 'month' && d.getMonth() !== range.month;
        const todaysClass = key === todayChina() ? ' today' : '';
        const dayEvents = byDate[key] || [];
        html += '<div class="day ' + (out ? 'out' : '') + todaysClass + '"><div class="day-num"><span>' + (d.getMonth() + 1) + '/' + d.getDate() + '</span></div>';
        dayEvents.slice(0, 5).forEach(e => {
            const label = compactTimeLabel(e);
            html += '<button class="event-pill p-' + esc(e.level || e.priority || 'B') + '" data-action="open-edit" data-event-key="' + esc(eventActionKey(e)) + '" title="' + esc((e.calendar_time_label || '') + ' · ' + (e.reason || e.title)) + '">' + (label ? '<strong>' + esc(label) + '</strong> ' : '') + esc(e.title) + '</button>';
        });
        if (dayEvents.length > 5) html += '<span class="more-pill">还有 ' + esc(dayEvents.length - 5) + ' 个</span>';
        if (dayEvents.length) html += '<button class="mini day-more" data-action="open-day-details" data-date-key="' + esc(key) + '">查看当天 <span class="day-count">(' + esc(dayEvents.length) + ')</span></button>';
        html += '</div>';
    });
    html += '</div>';
    if (!events.length) html = '<div class="empty"><strong>当前范围没有活动</strong><p>可以添加活动，或从公众号按时间范围批量提取。</p><div class="row-actions empty-actions"><button class="primary" data-action="open-modal" data-modal="extractModal">公众号提取</button><button data-action="open-modal" data-modal="addModal">添加活动</button></div></div>';
    root.innerHTML = html;
}

function renderList(events) {
    const root = document.getElementById('calendarRoot');
    if (!events.length) {
        root.innerHTML = '<div class="empty"><strong>暂无活动</strong><p>换一个筛选条件，或添加新的活动。</p></div>';
        return;
    }
    root.innerHTML = bulkDeleteToolbar(events) + '<div class="' + (currentView === 'cards' ? 'cards-view' : 'list-view') + '">' + events.map(eventCard).join('') + '</div>';
    updateBulkDeleteBar();
}
