function levelRank(e) {
    return ({ S: 0, A: 1, B: 2, C: 3 })[e.level || e.priority || 'B'] ?? 2;
}

function eventSortKey(e) {
    return String(e.calendar_time || e.start_time || e.registration_deadline || '');
}

function timeText(e) {
    const raw = String(e.calendar_time || e.start_time || e.registration_deadline || '');
    const m = raw.match(/(\d{1,2}[:：]\d{2}|\d{1,2}点(?:\d{1,2}分)?)/);
    return m ? m[0].replace('：', ':') : '待定';
}

function upNextItem(e) {
    return html`<button class="up-next-item" data-action="open-edit" data-event-key="${eventActionKey(e)}"><span>${timeText(e)}</span><strong>${e.title}</strong></button>`;
}

function renderSideRail(data) {
    const today = todayChina();
    const upNext = currentEvents
        .filter(e => eventDateKey(e) >= today)
        .sort((a, b) => eventSortKey(a).localeCompare(eventSortKey(b)))
        .slice(0, 4);
    document.getElementById('upNextEvents').innerHTML = upNext.map(upNextItem).join('') || '<div class="empty compact-empty"><strong>暂无即将开始的活动</strong></div>';
}

function compactTimeLabel(event) {
    const label = event.calendar_time_label || '';
    if (label.includes('报名开始')) return '报名';
    if (label.includes('报名截止')) return '截止';
    if (label.includes('活动开始')) return '开始';
    return label.slice(0, 2);
}

function eventActionKey(e) {
    return e.id || e._ui_key || eventDedupeKey(e);
}

function eventCard(e) {
    const tags = (e.tags || []).slice(0, 3).map(t => html`<span class="tag">${t}</span>`).join('');
    const calendarTime = e.calendar_time || e.start_time || '时间待定';
    const calendarLabel = e.calendar_time_label || (e.calendar_time ? '日历时间' : '活动时间');
    const fav = !!(e.is_favorite || e.favorite);
    const status = e.status || 'pending';
    const level = e.level || e.priority || 'B';
    const levelBadge = html`<span class="badge level level-${level}" title="${levelText(level)}">${level}</span>`;
    const duplicate = Number(e.duplicate_count || 1) > 1 ? html`<span class="badge duplicate-badge">+${Number(e.duplicate_count || 1) - 1} 来源</span>` : '';
    const favoriteText = fav ? '已收藏' : '收藏';
    const key = eventActionKey(e);
    const favoriteAction = e.id
        ? html`<button class="mini" data-action="toggle-favorite" data-event-id="${e.id}" data-favorite="${String(!fav)}">${favoriteText}</button>`
        : '<button class="mini" disabled>未同步</button>';
    const selectBox = e.id
        ? '<label class="event-select" data-action="stop-card-click"><input type="checkbox" data-action="toggle-event-selection" data-event-select="' + esc(e.id) + '" ' + (selectedEventIds.has(e.id) ? 'checked' : '') + '><span>选择</span></label>'
        : '';
    return '<article class="event-card" data-action="open-edit" data-event-key="' + esc(key) + '">' +
        '<div class="event-card-top"><div class="event-card-badges">' + levelBadge + duplicate + '</div><div class="event-card-state">' + selectBox + html`<span class="badge status-${status}">${statusText(status)}</span>` + '</div></div>' +
        html`<h3 class="event-title">${fav ? '★ ' : ''}${e.title}</h3>` +
        html`<div class="event-meta"><span>${calendarLabel + '：' + calendarTime}</span><span>${e.location || '地点待定'}</span><span>${e.source_name || e.account || '未知来源'}</span></div>` +
        (tags ? '<div class="tags">' + tags + '</div>' : '') +
        html`<div class="reason">${e.reason || '暂无推荐理由'}</div>` +
        '<div class="card-actions">' + html`<button class="mini primary-soft" data-action="open-edit" data-event-key="${key}">查看详情</button>` + favoriteAction + '<a class="btn mini" data-action="stop-card-click" href="/api/events/calendar.ics" target="_blank" rel="noopener">加入日历</a></div>' +
        '</article>';
}

function selectableCurrentEvents() {
    return currentEvents.filter(e => !!e.id);
}

function syncSelectionWithCurrentEvents() {
    const visibleIds = new Set(selectableCurrentEvents().map(e => e.id));
    selectedEventIds = new Set([...selectedEventIds].filter(id => visibleIds.has(id)));
}

function bulkDeleteToolbar(events) {
    const selectable = (events || []).filter(e => !!e.id);
    if (!selectable.length) return '';
    return '<div class="bulk-toolbar" id="bulkDeleteBar">' +
        '<div><strong id="bulkSelectedCount">已选 0 个</strong><span>可批量彻底删除当前列表中的活动</span></div>' +
        '<div class="row-actions bulk-actions"><button class="mini" data-action="select-all-visible-events">全选当前页</button><button class="mini" data-action="clear-event-selection">取消选择</button><button class="mini danger" data-action="bulk-delete-selected">删除已选</button></div>' +
        '</div>';
}

function toggleEventSelection(id, checked) {
    if (!id) return;
    if (checked) selectedEventIds.add(id);
    else selectedEventIds.delete(id);
    updateBulkDeleteBar();
}

function selectAllVisibleEvents() {
    selectableCurrentEvents().forEach(e => selectedEventIds.add(e.id));
    document.querySelectorAll('[data-event-select]').forEach(input => { input.checked = selectedEventIds.has(input.getAttribute('data-event-select')); });
    updateBulkDeleteBar();
}

function clearEventSelection() {
    selectedEventIds.clear();
    document.querySelectorAll('[data-event-select]').forEach(input => { input.checked = false; });
    updateBulkDeleteBar();
}

function updateBulkDeleteBar() {
    const count = selectedEventIds.size;
    const label = document.getElementById('bulkSelectedCount');
    const bar = document.getElementById('bulkDeleteBar');
    if (label) label.textContent = '已选 ' + count + ' 个';
    if (bar) bar.classList.toggle('has-selection', count > 0);
}
