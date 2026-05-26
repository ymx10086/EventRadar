let currentView = 'month';
let currentEvents = [];
let currentWeekStart = '';
let selectedEventIds = new Set();

function todayChina() {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const map = {};
    parts.forEach(p => map[p.type] = p.value);
    return map.year + '-' + map.month + '-' + map.day;
}

function localDateKey(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
}

function localMonthKey(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
}

function esc(value) {
    return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function lines(value) {
    return String(value || '').split(/[\n,，]/).map(s => s.trim()).filter(Boolean);
}

function normalizeDedupeText(value) {
    return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function eventDedupeKey(event) {
    if (event.id) return 'id:' + String(event.id);
    return [
        normalizeDedupeText(event.title),
        normalizeDedupeText(event.start_time || event.calendar_time || event.registration_deadline),
        normalizeDedupeText(event.location),
        normalizeDedupeText(event.source_name || event.account || event.source_url || event.source_article_url)
    ].join('|');
}

function dedupeEvents(events) {
    const map = new Map();
    for (const event of events || []) {
        const key = eventDedupeKey(event);
        if (!key || key === '|||') continue;
        const existing = map.get(key);
        if (!existing) {
            map.set(key, {
                ...event,
                _ui_key: key,
                duplicate_count: Number(event.duplicate_count || 1),
                duplicate_ids: event.id ? [event.id] : [],
                duplicate_sources: []
            });
            continue;
        }
        existing.duplicate_count = Math.max(Number(existing.duplicate_count || 1) + 1, 2);
        if (event.id && !existing.duplicate_ids.includes(event.id)) existing.duplicate_ids.push(event.id);
        const source = event.source_name || event.account || event.source_url || event.source_article_url || '';
        if (source && !existing.duplicate_sources.includes(source)) existing.duplicate_sources.push(source);
        existing.is_favorite = existing.is_favorite || event.is_favorite;
        existing.favorite = existing.favorite || event.favorite;
        existing.status = existing.status === 'confirmed' ? existing.status : (event.status || existing.status);
        existing.reason = existing.reason || event.reason;
        existing.description = existing.description || event.description;
    }
    return Array.from(map.values());
}

function eventDeleteIds(eventOrId) {
    if (!eventOrId) return [];
    const event = typeof eventOrId === 'string'
        ? currentEvents.find(item => item.id === eventOrId || item._ui_key === eventOrId)
        : eventOrId;
    if (!event) return typeof eventOrId === 'string' ? [eventOrId] : [];
    const ids = event.duplicate_ids && event.duplicate_ids.length ? event.duplicate_ids : [event.id];
    return [...new Set(ids.filter(Boolean))];
}

function removeDeletedEvents(ids) {
    const deleted = new Set(ids || []);
    if (!deleted.size) return;
    currentEvents = currentEvents
        .map(event => {
            const remainingIds = (event.duplicate_ids || [event.id]).filter(id => id && !deleted.has(id));
            if (remainingIds.length !== (event.duplicate_ids || [event.id]).filter(Boolean).length) {
                return { ...event, id: remainingIds[0] || event.id, duplicate_ids: remainingIds, duplicate_count: Math.max(remainingIds.length, 1) };
            }
            return event;
        })
        .filter(event => {
            const ids = event.duplicate_ids && event.duplicate_ids.length ? event.duplicate_ids : [event.id];
            return ids.some(id => id && !deleted.has(id));
        });
    deleted.forEach(id => selectedEventIds.delete(id));
    const range = activeRange();
    renderStats({ favorite_count: currentEvents.filter(e => e.is_favorite || e.favorite).length });
    if (currentView === 'list' || currentView === 'cards') renderList(currentEvents);
    else renderCalendar(currentEvents, range);
}

function normalizeDateInput(value) {
    const text = String(value || '').trim();
    if (!text) return todayChina();
    let match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (!match) match = text.match(/^(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})(?:日)?$/);
    if (!match) return '';
    return match[1] + '-' + String(match[2]).padStart(2, '0') + '-' + String(match[3]).padStart(2, '0');
}
