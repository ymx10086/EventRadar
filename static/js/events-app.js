function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function setPrimaryNavActive(sectionId) {
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.section === sectionId);
    });
}
function openImportNav() {
    showPage('app', 'page-calendar');
    setPrimaryNavActive('import');
    openModal('extractModal');
}
function openPreferenceNav() {
    showPage('app', 'page-calendar');
    setPrimaryNavActive('preference');
    openModal('profileModal');
    loadProfile();
}
function openSettingsNav() {
    showPage('app', 'page-calendar');
    setPrimaryNavActive('settings');
    openModal('settingsModal');
    loadSettings();
    loadRuns();
}
function showPage(page, sectionId) {
    document.querySelectorAll('.app-view, .product-page').forEach(el => el.classList.toggle('active', el.id === 'page-app'));
    document.querySelectorAll('.nav-item').forEach(el => {
        const isActive = el.dataset.page === 'app' && (!sectionId || el.dataset.section === sectionId);
        el.classList.toggle('active', isActive);
    });
    if (window.innerWidth <= 520 && !['list', 'cards'].includes(currentView)) setView('list');
    else loadEvents({ keepStatus: true });
    syncPrimaryNav(currentView);
    if (sectionId) {
        setTimeout(() => scrollToSection(sectionId), 40);
    } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}
function syncPrimaryNav(view) {
    const activeSection = view === 'month' || view === 'week' ? 'calendar-month' : 'activity-cards';
    document.querySelectorAll('.nav-item').forEach(el => {
        if (el.dataset.section) el.classList.toggle('active', el.dataset.section === activeSection);
    });
}
function openModal(id) {
    const modal = window.EventRadarModals?.ensureModal(id) || document.getElementById(id);
    if (!modal) return;
    if (id === 'extractModal') {
        const start = document.getElementById('extractStart');
        const end = document.getElementById('extractEnd');
        if (start && !start.value) start.value = todayChina();
        if (end && !end.value) end.value = todayChina();
    }
    modal.classList.add('is-open');
    document.body.classList.add('modal-open');
}
function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('is-open');
    if (!document.querySelector('.modal-backdrop.is-open')) document.body.classList.remove('modal-open');
}
document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = Array.from(document.querySelectorAll('.modal-backdrop.is-open')).pop();
    if (open) closeModal(open.id);
});
function setLine(id, text, type) {
    const el = document.getElementById(id);
    el.className = 'status-line ' + (type || '');
    el.textContent = text || '';
}
function levelText(level) {
    return ({ S: 'S 强相关', A: 'A 值得关注', B: 'B 一般相关', C: 'C 低相关' })[level] || 'B 一般相关';
}
function statusText(status) {
    return ({ pending: '待确认', confirmed: '已确认', ignored: '已忽略' })[status] || '待确认';
}
function eventDateKey(event) {
    const text = String(event.calendar_time || event.signup_start_time || event.registration_deadline || event.signup_deadline || event.start_time || '');
    let m = text.match(/\d{4}-\d{2}-\d{2}/);
    if (m) return m[0];
    m = text.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
    if (m) return m[1] + '-' + String(m[2]).padStart(2, '0') + '-' + String(m[3]).padStart(2, '0');
    m = text.match(/(\d{4})[/-](\d{1,2})[/-](\d{1,2})/);
    if (m) return m[1] + '-' + String(m[2]).padStart(2, '0') + '-' + String(m[3]).padStart(2, '0');
    const fallbackYear = (event.source_publish_time || '').match(/\b(20\d{2})\b/)?.[1] || document.getElementById('monthInput').value.slice(0, 4) || todayChina().slice(0, 4);
    m = text.match(/(\d{1,2})月\s*(\d{1,2})(?:日)?/);
    if (m) return fallbackYear + '-' + String(m[1]).padStart(2, '0') + '-' + String(m[2]).padStart(2, '0');
    m = text.match(/(?<!\d)(\d{1,2})[/-](\d{1,2})(?!\d)/);
    if (m) return fallbackYear + '-' + String(m[1]).padStart(2, '0') + '-' + String(m[2]).padStart(2, '0');
    return '';
}
function monthRange() {
    const value = document.getElementById('monthInput').value || todayChina().slice(0, 7);
    const base = new Date(value + '-01T00:00:00');
    const y = base.getFullYear();
    const m = base.getMonth();
    return {
        year: y,
        month: m,
        start: localDateKey(new Date(y, m, 1)),
        end: localDateKey(new Date(y, m + 1, 0)),
        label: y + '年' + String(m + 1).padStart(2, '0') + '月'
    };
}
function weekRange() {
    const value = document.getElementById('monthInput').value || todayChina().slice(0, 7);
    const today = new Date(todayChina() + 'T00:00:00');
    const base = currentWeekStart ? new Date(currentWeekStart + 'T00:00:00') : (localMonthKey(today) === value ? today : new Date(value + '-01T00:00:00'));
    const day = (base.getDay() + 6) % 7;
    const start = new Date(base);
    start.setDate(base.getDate() - day);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    currentWeekStart = localDateKey(start);
    document.getElementById('monthInput').value = localMonthKey(start);
    return { start: localDateKey(start), end: localDateKey(end), label: localDateKey(start) + ' 至 ' + localDateKey(end), startDate: start };
}
function activeRange() { return currentView === 'week' ? weekRange() : monthRange(); }
function viewDescription(view) {
    return {
        month: '按月份查看活动分布，适合快速扫一眼本月节奏。',
        week: '聚焦本周活动，用来安排近期要确认和参加的事项。',
        list: '按列表查看所有活动，适合搜索、筛选和批量处理。',
        cards: '以卡片浏览活动推荐，点击卡片查看完整详情。'
    }[view] || '浏览你的活动日历。';
}
function setView(view) {
    currentView = view;
    if (view === 'week' && !currentWeekStart) {
        const selectedMonth = document.getElementById('monthInput').value || todayChina().slice(0, 7);
        currentWeekStart = selectedMonth === todayChina().slice(0, 7) ? todayChina() : selectedMonth + '-01';
    }
    ['month', 'week', 'list', 'cards'].forEach(v => {
        document.getElementById('view-' + v)?.classList.toggle('active', v === view);
        document.getElementById('viewTop-' + v)?.classList.toggle('active', v === view);
    });
    document.getElementById('modeDescription').textContent = viewDescription(view);
    syncPrimaryNav(view);
    loadEvents();
}
function handleMonthChange() {
    const value = document.getElementById('monthInput').value || todayChina().slice(0, 7);
    currentWeekStart = currentView === 'week' ? value + '-01' : '';
    loadEvents();
}
function moveRange(delta) {
    const input = document.getElementById('monthInput');
    if (currentView === 'week') {
        const base = new Date((currentWeekStart || todayChina()) + 'T00:00:00');
        base.setDate(base.getDate() + delta * 7);
        currentWeekStart = localDateKey(base);
        input.value = localMonthKey(base);
        loadEvents();
        return;
    }
    const base = new Date((input.value || todayChina().slice(0, 7)) + '-01T00:00:00');
    base.setMonth(base.getMonth() + delta);
    currentWeekStart = '';
    input.value = localMonthKey(base);
    loadEvents();
}
function jumpToday() {
    document.getElementById('monthInput').value = todayChina().slice(0, 7);
    currentWeekStart = todayChina();
    loadEvents();
}
function clearFilters() {
    document.getElementById('levelFilter').value = '';
    document.getElementById('tagFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('keywordInput').value = '';
    document.getElementById('favoriteFilter').value = '';
    setLine('calendarStatus', '');
    loadEvents();
}
async function loadEvents(options) {
    options = options || {};
    if (!options.keepStatus) setLine('calendarStatus', '');
    if (currentView !== 'week') currentWeekStart = '';
    const range = activeRange();
    const params = new URLSearchParams();
    params.set('start', range.start);
    params.set('end', range.end);
    const level = document.getElementById('levelFilter').value;
    const tag = document.getElementById('tagFilter').value;
    const status = document.getElementById('statusFilter').value;
    const q = document.getElementById('keywordInput').value.trim();
    const favorite = document.getElementById('favoriteFilter').value;
    if (level) params.set('priority', level);
    if (tag) params.set('tag', tag);
    if (status) params.set('status', status);
    if (status === 'ignored') params.set('include_ignored', 'true');
    if (q) params.set('q', q);
    if (favorite === 'favorite') params.set('favorite', 'true');
    if (favorite === 'unfavorite') params.set('favorite', 'false');
    const res = await fetch('/api/events/list?' + params.toString());
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.detail || '活动读取失败');
    currentEvents = dedupeEvents(data.data.events || []);
    if (favorite === 'favorite') currentEvents = currentEvents.filter(e => e.is_favorite || e.favorite);
    if (favorite === 'unfavorite') currentEvents = currentEvents.filter(e => !(e.is_favorite || e.favorite));
    syncSelectionWithCurrentEvents();
    renderStats(data.data || {});
    renderTagOptions(data.data.tags || []);
    document.getElementById('rangeTitle').textContent = range.label;
    if (currentView === 'list' || currentView === 'cards') renderList(currentEvents);
    else renderCalendar(currentEvents, range);
}
async function bulkDeleteSelected() {
    const ids = [...new Set([...selectedEventIds].flatMap(id => eventDeleteIds(id)))];
    if (!ids.length) return setLine('calendarStatus', '请先选择要删除的活动', 'err');
    if (!window.confirm('确定要彻底删除已选的 ' + ids.length + ' 个活动吗？这会从活动库、日历和 ICS 中移除。')) return;
    try {
        const result = await requestDeleteEvents(ids);
        selectedEventIds.clear();
        removeDeletedEvents(result.deleted_ids || ids);
        await loadEvents({ keepStatus: true });
        setLine('calendarStatus', '已彻底删除 ' + (result.deleted_count || ids.length) + ' 个活动', 'ok');
    } catch (err) {
        setLine('calendarStatus', err.message || '批量删除失败', 'err');
    }
}
async function toggleFavorite(id, favorite) {
    await fetch('/api/events/' + encodeURIComponent(id) + '/favorite?favorite=' + String(!!favorite), { method: 'POST' });
    loadEvents();
}
function openEdit(id) {
    const e = currentEvents.find(item => item.id === id || item._ui_key === id);
    if (!e) return;
    window.EventRadarModals?.ensureModal('editModal');
    document.getElementById('editId').value = e.id || '';
    document.getElementById('editTitle').value = e.title || '';
    document.getElementById('editTags').value = (e.tags || []).join('，');
    document.getElementById('editStart').value = e.start_time || '';
    document.getElementById('editEnd').value = e.end_time || '';
    document.getElementById('editLocation').value = e.location || '';
    document.getElementById('editCity').value = e.city || '';
    document.getElementById('editLevel').value = e.level || e.priority || 'B';
    document.getElementById('editStatus').value = e.status || 'pending';
    document.getElementById('editDeadline').value = e.registration_deadline || e.signup_deadline || '';
    document.getElementById('editRegLink').value = e.registration_link || e.signup_url || '';
    document.getElementById('editReason').value = e.reason || '';
    document.getElementById('editDesc').value = e.description || '';
    const summary = [
        e.calendar_time || e.start_time || '时间待定',
        e.location || '地点待定',
        e.source_name || e.account || '未知来源',
        levelText(e.level || e.priority || 'B'),
        statusText(e.status || 'pending')
    ];
    document.getElementById('editSummary').innerHTML = summary.map(item => '<span>' + esc(item) + '</span>').join('');
    const sourceUrl = e.source_url || e.source_article_url || '';
    const sourceRow = document.getElementById('editSourceRow');
    const sourceLink = document.getElementById('editSourceLink');
    if (sourceUrl) {
        sourceRow.classList.remove('is-hidden');
        sourceLink.href = sourceUrl;
        sourceLink.textContent = '打开公众号原文';
    } else {
        sourceRow.classList.add('is-hidden');
        sourceLink.href = '#';
    }
    const duplicateInfo = document.getElementById('editDuplicateInfo');
    const duplicateCount = Number(e.duplicate_count || 1);
    duplicateInfo.textContent = duplicateCount > 1 ? '已合并 ' + duplicateCount + ' 个重复来源' : '';
    duplicateInfo.className = 'status-line ' + (duplicateCount > 1 ? 'ok' : '');
    const deleteBtn = document.getElementById('deleteCurrentBtn');
    if (deleteBtn) {
        deleteBtn.disabled = !e.id;
        deleteBtn.textContent = e.id ? '彻底删除' : '未同步，不能删除';
    }
    setLine('editStatusLine', '');
    openModal('editModal');
}
async function quickUpdate(id, updates) {
    const beforeFilter = document.getElementById('statusFilter').value;
    const res = await fetch('/api/events/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updates) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('calendarStatus', data.detail || '更新失败', 'err');
    await loadEvents({ keepStatus: true });
    const nextStatus = updates.status || (data.data && data.data.event && data.data.event.status) || '';
    let msg = nextStatus ? '已更新为“' + statusText(nextStatus) + '”' : '已更新活动';
    if (beforeFilter && nextStatus && beforeFilter !== nextStatus) {
        msg += '。当前筛选是“' + statusText(beforeFilter) + '”，所以这条活动会从当前视图移走。';
    } else if (nextStatus === 'ignored') {
        msg += '，默认日历会隐藏它。';
    } else if (nextStatus === 'confirmed') {
        msg += '，后续重复导入会保留这个确认状态。';
    }
    setLine('calendarStatus', msg, 'ok');
}
async function deleteEvent(id, title) {
    const name = title || '这个活动';
    const ids = eventDeleteIds(id);
    const duplicateNote = ids.length > 1 ? '，包含已合并的 ' + ids.length + ' 条重复记录' : '';
    if (!window.confirm('确定要彻底删除“' + name + '”吗？这不是忽略，删除后会从活动库、日历和 ICS 中移除' + duplicateNote + '。')) return;
    try {
        const result = await requestDeleteEvents(ids);
        removeDeletedEvents(result.deleted_ids || ids);
        await loadEvents({ keepStatus: true });
        setLine('calendarStatus', '已彻底删除“' + name + '”', 'ok');
    } catch (err) {
        setLine('calendarStatus', err.message || '删除失败', 'err');
    }
}
async function deleteCurrentEvent() {
    const id = document.getElementById('editId').value;
    const title = document.getElementById('editTitle').value;
    const event = currentEvents.find(item => item.id === id || item._ui_key === id);
    const ids = eventDeleteIds(event || id);
    if (!ids.length) return setLine('editStatusLine', '这个活动缺少数据库 ID，无法彻底删除。请刷新列表后再试。', 'err');
    const name = title || '这个活动';
    const duplicateNote = ids.length > 1 ? '，包含已合并的 ' + ids.length + ' 条重复记录' : '';
    if (!window.confirm('确定要彻底删除“' + name + '”吗？这不是忽略，删除后会从活动库、日历和 ICS 中移除' + duplicateNote + '。')) return;
    try {
        const result = await requestDeleteEvents(ids);
        closeModal('editModal');
        removeDeletedEvents(result.deleted_ids || ids);
        await loadEvents({ keepStatus: true });
        setLine('calendarStatus', '已彻底删除“' + name + '”', 'ok');
    } catch (err) {
        setLine('editStatusLine', err.message || '删除失败', 'err');
    }
}
async function saveEdit() {
    const id = document.getElementById('editId').value;
    const body = {
        title: document.getElementById('editTitle').value,
        tags: lines(document.getElementById('editTags').value),
        start_time: document.getElementById('editStart').value,
        end_time: document.getElementById('editEnd').value,
        location: document.getElementById('editLocation').value,
        city: document.getElementById('editCity').value,
        level: document.getElementById('editLevel').value,
        status: document.getElementById('editStatus').value,
        registration_deadline: document.getElementById('editDeadline').value,
        registration_link: document.getElementById('editRegLink').value,
        reason: document.getElementById('editReason').value,
        description: document.getElementById('editDesc').value
    };
    const res = await fetch('/api/events/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('editStatusLine', data.detail || '保存失败', 'err');
    setLine('editStatusLine', '已保存', 'ok');
    loadEvents();
}
async function saveManualEvent() {
    const file = document.getElementById('manualImage').files[0];
    const body = {
        mode: document.getElementById('manualMode').value,
        pasted_text: document.getElementById('manualText').value,
        link: document.getElementById('manualLink').value,
        image_path: file ? file.name : '',
        title: document.getElementById('manualTitle').value,
        start_time: document.getElementById('manualStart').value,
        end_time: document.getElementById('manualEnd').value,
        location: document.getElementById('manualLocation').value,
        city: document.getElementById('manualCity').value,
        organizer: document.getElementById('manualOrganizer').value,
        description: document.getElementById('manualDesc').value,
        registration_deadline: document.getElementById('manualDeadline').value,
        registration_link: document.getElementById('manualRegLink').value,
        tags: lines(document.getElementById('manualTags').value),
        level: document.getElementById('manualLevel').value || null
    };
    const res = await fetch('/api/events/manual', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('manualStatus', data.detail || '保存失败', 'err');
    setLine('manualStatus', '已保存到我的活动日历', 'ok');
    loadEvents();
}
async function runAccountRange() {
    const btn = document.getElementById('extractBtn');
    btn.disabled = true;
    setLine('extractStatus', '任务已提交，下面会实时显示抓取进度。');
    resetExtractProgress();
    const startDate = normalizeDateInput(document.getElementById('extractStart').value);
    const endDate = normalizeDateInput(document.getElementById('extractEnd').value || document.getElementById('extractStart').value);
    if (!startDate || !endDate) {
        setLine('extractStatus', '日期格式请使用 2026-05-21，留空则默认今天。', 'err');
        btn.disabled = false;
        return;
    }
    const body = {
        account: document.getElementById('extractAccount').value,
        start_date: startDate,
        end_date: endDate,
        use_llm: document.getElementById('extractLlm').value === 'true',
        use_vision: document.getElementById('extractVision').value === 'true'
    };
    try {
        const res = await fetch('/api/events/run-account-range/progress', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(humanError(data.detail) || '提取失败');
        await pollExtractJob(data.data.job_id);
    } catch (err) {
        setLine('extractStatus', err.message || String(err), 'err');
        btn.disabled = false;
    }
}
function humanError(detail) {
    if (Array.isArray(detail)) {
        const dateError = detail.find(item => item.type === 'string_pattern_mismatch' && String(item.loc || '').includes('date'));
        if (dateError) return '日期格式请使用 2026-05-21，留空则默认今天。';
        return detail.map(item => item.msg || String(item)).join('；');
    }
    return detail || '';
}
function resetExtractProgress() {
    document.getElementById('extractProgress').classList.add('open');
    document.getElementById('extractProgressFill').style.width = '1%';
    document.getElementById('extractProgressMessage').textContent = '任务已创建，等待开始抓取';
    document.getElementById('extractProgressLog').innerHTML = '';
}
function renderExtractJob(job) {
    document.getElementById('extractProgress').classList.add('open');
    document.getElementById('extractProgressFill').style.width = (job.percent || 0) + '%';
    document.getElementById('extractProgressMessage').textContent =
        (job.percent || 0) + '% · ' + (job.message || '处理中');
    document.getElementById('extractProgressLog').innerHTML = (job.logs || []).slice(-12).reverse().map(log => {
        const time = log.at ? new Date(log.at * 1000).toLocaleTimeString() : '';
        return '<div>' + esc(time) + ' · ' + esc(log.stage || '') + ' · ' + esc(log.message || '') + '</div>';
    }).join('');
}
async function pollExtractJob(jobId) {
    const btn = document.getElementById('extractBtn');
    while (true) {
        const res = await fetch('/api/events/jobs/' + encodeURIComponent(jobId));
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.detail || '进度读取失败');
        const job = data.data.job;
        renderExtractJob(job);
        if (job.status === 'success') {
            const result = job.result || {};
            setLine('extractStatus', '完成：文章 ' + (result.article_count || 0) + ' 篇，活动 ' + (result.event_count || 0) + ' 个，已保存 ' + (result.saved_count || 0) + ' 个', 'ok');
            btn.disabled = false;
            loadEvents();
            return;
        }
        if (job.status === 'failed') {
            setLine('extractStatus', job.error || job.message || '提取失败', 'err');
            btn.disabled = false;
            return;
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}
async function loadSources() {
    const res = await fetch('/api/events/sources');
    const data = await res.json();
    const list = data.data.sources || [];
    document.getElementById('sourceList').innerHTML = list.map(s => '<div class="source-row"><div><strong>' + esc(s.name) + '</strong><p>' + esc(s.source_type) + ' · ' + esc(s.alias || s.fakeid || s.url || '') + ' · ' + (s.auto_fetch ? '参与定时抓取' : '不参与定时抓取') + '</p></div><div class="row-actions"><button class="mini" data-action="toggle-source-auto-fetch" data-source-id="' + esc(s.id) + '" data-auto-fetch="' + String(!s.auto_fetch) + '">' + (s.auto_fetch ? '暂停定时' : '加入定时') + '</button><button class="mini" data-action="delete-source" data-source-id="' + esc(s.id) + '">删除</button></div></div>').join('') || '<div class="empty"><strong>暂无信息源</strong></div>';
}
async function toggleSourceAutoFetch(id, autoFetch) {
    const res = await fetch('/api/events/sources/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auto_fetch: !!autoFetch }) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('sourceStatus', data.detail || '更新失败', 'err');
    loadSources();
}
async function addSource() {
    const body = {
        source_type: document.getElementById('sourceType').value,
        name: document.getElementById('sourceName').value,
        fakeid: document.getElementById('sourceFakeid').value,
        url: document.getElementById('sourceUrl').value
    };
    setLine('sourceStatus', body.source_type === 'wechat' ? '正在搜索公众号并解析 fakeid...' : '正在添加链接源...');
    const res = await fetch('/api/events/sources', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('sourceStatus', data.detail || '添加失败', 'err');
    setLine('sourceStatus', '已添加信息源', 'ok');
    loadSources();
}
async function deleteSource(id) {
    await fetch('/api/events/sources/' + encodeURIComponent(id), { method: 'DELETE' });
    loadSources();
}
async function loadProfile() {
    const data = await (await fetch('/api/events/profile')).json();
    const p = data.data.profile || {};
    document.getElementById('profileIdentity').value = p.identity || '';
    document.getElementById('profileProfession').value = p.profession || '';
    document.getElementById('profileResearch').value = p.research_direction || '';
    document.getElementById('profileInterests').value = (p.interests || []).join('\n');
    document.getElementById('profileKeywords').value = (p.priority_keywords || []).join('\n');
    document.getElementById('profileAvoid').value = (p.avoid_topics || []).join('\n');
}
async function saveProfile() {
    const body = {
        identity: document.getElementById('profileIdentity').value,
        profession: document.getElementById('profileProfession').value,
        research_direction: document.getElementById('profileResearch').value,
        interests: lines(document.getElementById('profileInterests').value),
        priority_keywords: lines(document.getElementById('profileKeywords').value),
        avoid_topics: lines(document.getElementById('profileAvoid').value)
    };
    const res = await fetch('/api/events/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    setLine('profileStatus', data.success ? '已保存画像，后续活动会按新画像分级' : (data.detail || '保存失败'), data.success ? 'ok' : 'err');
}
async function loadSettings() {
    const data = await (await fetch('/api/events/settings')).json();
    const s = data.data.settings || {};
    const automation = data.data.automation || {};
    const safety = data.data.fetch_safety || automation.fetch_safety || {};
    document.getElementById('settingEnabled').value = String(!!s.daily_fetch_enabled);
    document.getElementById('settingTime').value = s.daily_fetch_time || '07:30';
    document.getElementById('settingLookbackDays').value = s.daily_fetch_lookback_days || 0;
    document.getElementById('settingRetentionDays').value = s.event_retention_days || 15;
    document.getElementById('settingImport').value = String(s.auto_import_calendar !== false);
    document.getElementById('settingLlm').value = String(s.use_llm !== false);
    document.getElementById('settingVision').value = String(!!s.use_vision);
    document.getElementById('settingMaxChars').value = s.max_chars || 9000;
    document.getElementById('settingFetchConcurrency').value = s.wechat_fetch_concurrency || 1;
    document.getElementById('settingFetchDelayMin').value = s.wechat_fetch_delay_min ?? 3;
    document.getElementById('settingFetchDelayMax').value = s.wechat_fetch_delay_max ?? 8;
    document.getElementById('settingAccountDelay').value = s.wechat_account_delay ?? 10;
    document.getElementById('settingMaxArticlesPerAccount').value = s.wechat_max_articles_per_account || 20;
    document.getElementById('settingVerificationPause').value = s.wechat_verification_pause_minutes ?? 30;
    document.getElementById('settingVerificationThreshold').value = s.wechat_verification_stop_threshold || 2;
    document.getElementById('settingProxyRequired').value = String(!!s.wechat_proxy_required);
    renderFetchSafetyStatus(safety);
    renderAutomationProgress(automation.progress || {});
}
async function saveSettings() {
    const body = {
        daily_fetch_enabled: document.getElementById('settingEnabled').value === 'true',
        daily_fetch_time: document.getElementById('settingTime').value || '07:30',
        daily_fetch_lookback_days: Number(document.getElementById('settingLookbackDays').value || 0),
        event_retention_days: Number(document.getElementById('settingRetentionDays').value || 15),
        auto_import_calendar: document.getElementById('settingImport').value === 'true',
        use_llm: document.getElementById('settingLlm').value === 'true',
        use_vision: document.getElementById('settingVision').value === 'true',
        max_chars: Number(document.getElementById('settingMaxChars').value || 9000),
        wechat_fetch_concurrency: Number(document.getElementById('settingFetchConcurrency').value || 1),
        wechat_fetch_delay_min: Number(document.getElementById('settingFetchDelayMin').value || 0),
        wechat_fetch_delay_max: Number(document.getElementById('settingFetchDelayMax').value || 0),
        wechat_account_delay: Number(document.getElementById('settingAccountDelay').value || 0),
        wechat_max_articles_per_account: Number(document.getElementById('settingMaxArticlesPerAccount').value || 20),
        wechat_verification_pause_minutes: Number(document.getElementById('settingVerificationPause').value || 0),
        wechat_verification_stop_threshold: Number(document.getElementById('settingVerificationThreshold').value || 2),
        wechat_proxy_required: document.getElementById('settingProxyRequired').value === 'true'
    };
    const res = await fetch('/api/events/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    setLine('settingsStatus', data.success ? '设置已保存' : (data.detail || '保存失败'), data.success ? 'ok' : 'err');
    if (data.success) renderFetchSafetyStatus((data.data && data.data.fetch_safety) || {});
}
async function runAutomationNow() {
    setLine('settingsStatus', '正在执行定时抓取流程...');
    resetAutomationProgress();
    const promise = fetch('/api/automation/run-events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ poll: true, lookback_days: Number(document.getElementById('settingLookbackDays').value || 0) }) });
    await pollAutomationProgress(true);
    const res = await promise;
    const data = await res.json();
    setLine('settingsStatus', data.success ? '抓取完成' : (data.detail || '抓取失败'), data.success ? 'ok' : 'err');
    loadRuns();
    loadEvents();
}
async function cleanupDuplicateEvents() {
    setLine('settingsStatus', '正在清理重复活动...');
    const res = await fetch('/api/events/cleanup-duplicates', { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('settingsStatus', data.detail || '清理失败', 'err');
    setLine('settingsStatus', '已清理重复活动 ' + (data.data.deleted_count || 0) + ' 条', 'ok');
    loadEvents();
}
async function cleanupOldEvents() {
    const retentionDays = Number(document.getElementById('settingRetentionDays').value || 15);
    setLine('settingsStatus', '正在清理过期未收藏活动...');
    const res = await fetch('/api/events/cleanup?retention_days=' + encodeURIComponent(retentionDays), { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('settingsStatus', data.detail || '清理失败', 'err');
    setLine('settingsStatus', '已清理过期活动 ' + (data.data.deleted_count || 0) + ' 条，文件 ' + (data.data.deleted_file_count || 0) + ' 个', 'ok');
    loadEvents();
}
function resetAutomationProgress() {
    document.getElementById('automationProgress').classList.add('open');
    document.getElementById('automationProgressFill').style.width = '1%';
    document.getElementById('automationProgressMessage').textContent = '任务已提交，等待开始';
    document.getElementById('automationProgressLog').innerHTML = '';
}
function renderAutomationProgress(progress) {
    const box = document.getElementById('automationProgress');
    if (!box) return;
    if (!progress || (!progress.active && !progress.updated_at)) {
        box.classList.remove('open');
        return;
    }
    box.classList.add('open');
    document.getElementById('automationProgressFill').style.width = (progress.percent || 0) + '%';
    document.getElementById('automationProgressMessage').textContent =
        (progress.percent || 0) + '% · ' + (progress.message || '处理中');
    document.getElementById('automationProgressLog').innerHTML = (progress.logs || []).slice(-12).reverse().map(log => {
        const time = log.at ? new Date(log.at * 1000).toLocaleTimeString() : '';
        return '<div>' + esc(time) + ' · ' + esc(log.stage || '') + ' · ' + esc(log.message || '') + '</div>';
    }).join('');
}
function renderFetchSafetyStatus(safety) {
    const el = document.getElementById('fetchSafetyStatus');
    if (!el) return;
    const proxy = safety.proxy_pool || {};
    const cfg = safety.config || {};
    const bits = [
        safety.paused ? ('冷却中，剩余 ' + Math.ceil((safety.cooldown_remaining_seconds || 0) / 60) + ' 分钟') : '防风控状态正常',
        '代理 ' + (proxy.enabled ? (proxy.healthy + '/' + proxy.total + ' 可用') : '未启用'),
        '并发 ' + (cfg.article_concurrency || '-'),
        '间隔 ' + (cfg.article_delay_min ?? '-') + '-' + (cfg.article_delay_max ?? '-') + ' 秒'
    ];
    el.className = 'status-line ' + (safety.paused ? 'err' : 'ok');
    el.textContent = bits.join(' · ');
}
function formatDateTime(ts) {
    return ts ? new Date(ts * 1000).toLocaleString() : '-';
}
function formatShortDateTime(ts) {
    return ts ? new Date(ts * 1000).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-';
}
function accountNames(accounts) {
    const names = (accounts || []).map(item => item.nickname || item.fakeid || '').filter(Boolean);
    return names.length ? names.join('、') : '未记录来源';
}
function renderRecordArticle(article) {
    const time = article.publish_time ? formatShortDateTime(article.publish_time) : (article.fetched_at ? formatShortDateTime(article.fetched_at) : '-');
    const account = article.account_name || article.account_alias || article.fakeid || '未知来源';
    const link = article.link
        ? '<a class="btn mini" href="' + esc(article.link) + '" target="_blank" rel="noopener">原文</a>'
        : '<span class="record-muted">无链接</span>';
    return '<div class="record-article">' +
        '<div class="article-time">' + esc(time) + '</div>' +
        '<div class="article-main"><strong title="' + esc(article.title || '') + '">' + esc(article.title || '未命名文章') + '</strong><p>' + esc(account) + (article.image_count ? ' · ' + esc(article.image_count) + ' 张图' : '') + '</p></div>' +
        '<div class="article-action">' + link + '</div>' +
        '</div>';
}
function renderFetchRecord(record) {
    const ok = record.status === 'success';
    const articles = record.articles || [];
    const dateRange = (record.start_date && record.end_date && record.start_date !== record.end_date)
        ? record.start_date + ' - ' + record.end_date
        : (record.date || record.start_date || '-');
    return '<article class="fetch-record-card">' +
        '<div class="record-head">' +
            '<div><span class="badge ' + (ok ? 'status-confirmed' : 'status-ignored') + '">' + esc(ok ? '成功' : '失败') + '</span><h3>' + esc(formatDateTime(record.started_at)) + '</h3><p>' + esc(dateRange) + ' · 耗时 ' + esc(record.duration_seconds || 0) + 's</p></div>' +
            '<div class="record-metrics"><span><strong>' + esc(record.article_count || 0) + '</strong>文章</span><span><strong>' + esc(record.event_count || 0) + '</strong>活动</span><span><strong>' + esc(record.saved_count || 0) + '</strong>入库</span></div>' +
        '</div>' +
        '<div class="record-source-line">来源：' + esc(accountNames(record.selected_accounts)) + '</div>' +
        (record.error ? '<div class="status-line err">' + esc(record.error) + '</div>' : '') +
        '<details class="record-articles" open><summary>本次抓取文章 ' + esc(articles.length) + (record.articles_truncated ? '+' : '') + ' 篇</summary>' +
        '<div class="record-article-list">' + (articles.length ? articles.map(renderRecordArticle).join('') : '<div class="empty compact-empty"><strong>没有找到文章归档</strong><p>旧记录可能没有生成 daily archive，或归档文件已被清理。</p></div>') + '</div>' +
        '</details>' +
        '</article>';
}
async function loadFetchRecords() {
    const status = document.getElementById('fetchRecordsStatus');
    const list = document.getElementById('fetchRecordsList');
    if (!status || !list) return;
    status.className = 'status-line';
    status.textContent = '正在读取抓取记录...';
    try {
        const res = await fetch('/api/automation/fetch-records?limit=20&articles_per_run=120');
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.detail || '读取失败');
        const records = (data.data && data.data.records) || [];
        list.innerHTML = records.map(renderFetchRecord).join('') || '<div class="empty"><strong>暂无抓取记录</strong><p>运行一次自动抓取后，这里会显示文章清单和抽取结果。</p></div>';
        status.textContent = records.length ? '共 ' + records.length + ' 次记录' : '';
    } catch (err) {
        status.textContent = err.message || String(err);
        status.className = 'status-line err';
    }
}
function openFetchRecords() {
    openModal('fetchRecordsModal');
    loadFetchRecords();
}
function handleAppAction(action, target, event) {
    const modal = target.dataset.modal;
    const view = target.dataset.view;
    switch (action) {
        case 'show-calendar':
            showPage('app', 'page-calendar');
            setView('month');
            break;
        case 'show-activity':
            showPage('app', 'page-calendar');
            setView('cards');
            break;
        case 'open-import-nav':
            openImportNav();
            break;
        case 'open-preference-nav':
            openPreferenceNav();
            break;
        case 'open-settings-nav':
            openSettingsNav();
            break;
        case 'set-view':
            if (view) setView(view);
            break;
        case 'move-range':
            moveRange(Number(target.dataset.delta || 0));
            break;
        case 'jump-today':
            jumpToday();
            break;
        case 'load-events':
            loadEvents();
            break;
        case 'clear-filters':
            clearFilters();
            break;
        case 'open-modal':
            if (modal) openModal(modal);
            break;
        case 'close-modal':
            if (modal) closeModal(modal);
            break;
        case 'open-sources':
            openModal('sourcesModal');
            loadSources();
            break;
        case 'save-manual-event':
            saveManualEvent();
            break;
        case 'run-account-range':
            runAccountRange();
            break;
        case 'add-source':
            addSource();
            break;
        case 'save-profile':
            saveProfile();
            break;
        case 'open-fetch-records':
            openFetchRecords();
            break;
        case 'save-settings':
            saveSettings();
            break;
        case 'run-automation-now':
            runAutomationNow();
            break;
        case 'cleanup-old-events':
            cleanupOldEvents();
            break;
        case 'cleanup-duplicate-events':
            cleanupDuplicateEvents();
            break;
        case 'load-fetch-records':
            loadFetchRecords();
            break;
        case 'save-edit':
            saveEdit();
            break;
        case 'delete-current-event':
            deleteCurrentEvent();
            break;
        case 'open-edit':
            event?.stopPropagation();
            if (target.dataset.eventKey) openEdit(target.dataset.eventKey);
            break;
        case 'open-day-details':
            if (target.dataset.dateKey) openDayDetails(target.dataset.dateKey);
            break;
        case 'toggle-favorite':
            event?.stopPropagation();
            if (target.dataset.eventId) toggleFavorite(target.dataset.eventId, target.dataset.favorite === 'true');
            break;
        case 'stop-card-click':
            event?.stopPropagation();
            break;
        case 'select-all-visible-events':
            selectAllVisibleEvents();
            break;
        case 'clear-event-selection':
            clearEventSelection();
            break;
        case 'bulk-delete-selected':
            bulkDeleteSelected();
            break;
        case 'toggle-event-selection':
            event?.stopPropagation();
            toggleEventSelection(target.dataset.eventSelect, target.checked);
            break;
        case 'toggle-source-auto-fetch':
            if (target.dataset.sourceId) toggleSourceAutoFetch(target.dataset.sourceId, target.dataset.autoFetch === 'true');
            break;
        case 'delete-source':
            if (target.dataset.sourceId) deleteSource(target.dataset.sourceId);
            break;
        case 'change-month':
            handleMonthChange();
            break;
        case 'search-keyword':
            if (event && event.key === 'Enter') loadEvents();
            break;
        default:
            break;
    }
}
function bindStaticActions() {
    document.addEventListener('click', event => {
        const target = event.target.closest('[data-action]');
        if (!target || !target.dataset.action) return;
        if (target.matches('input, select, textarea')) return;
        if (target.dataset.action !== 'stop-card-click') event.preventDefault();
        handleAppAction(target.dataset.action, target, event);
    });
    document.addEventListener('change', event => {
        const target = event.target.closest('[data-action]');
        if (!target || !target.dataset.action) return;
        handleAppAction(target.dataset.action, target, event);
    });
    document.addEventListener('keydown', event => {
        const target = event.target.closest('[data-action]');
        if (!target || !target.dataset.action) return;
        handleAppAction(target.dataset.action, target, event);
    });
}
async function pollAutomationProgress(stopWhenIdle) {
    let seenActive = false;
    let idleChecks = 0;
    while (true) {
        const res = await fetch('/api/automation/status');
        const data = await res.json();
        const progress = (data.data && data.data.progress) || {};
        const safety = (data.data && data.data.fetch_safety) || {};
        renderAutomationProgress(progress);
        renderFetchSafetyStatus(safety);
        if (progress.active) seenActive = true;
        if (!progress.active && stopWhenIdle && seenActive) return;
        if (!progress.active && stopWhenIdle && !seenActive && ++idleChecks >= 5) return;
        if (!stopWhenIdle) return;
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}
async function loadRuns() {
    const res = await fetch('/api/automation/runs?limit=8');
    const data = await res.json();
    const runs = (data.data && data.data.runs) || [];
    document.getElementById('runLog').innerHTML = runs.map(r => {
        const result = r.result || {};
        const archive = result.archive || {};
        const events = result.events || {};
        return '<div class="log-row"><div><strong>' + esc(r.status === 'success' ? '抓取成功' : '抓取失败') + '</strong><p>' + esc(formatDateTime(r.started_at)) + ' · ' + esc(r.duration_seconds || 0) + 's · ' + esc(archive.article_count || events.article_count || 0) + ' 篇文章 · ' + esc(events.event_count || 0) + ' 个活动' + (r.error ? ' · ' + esc(r.error) : '') + '</p></div></div>';
    }).join('') || '<div class="empty"><strong>暂无抓取日志</strong></div>';
}
function syncFilterDrawer() {
    const drawer = document.getElementById('filtersDrawer');
    if (!drawer) return;
    drawer.open = false;
}
bindStaticActions();
window.addEventListener('resize', syncFilterDrawer);
syncFilterDrawer();
document.getElementById('monthInput').value = todayChina().slice(0, 7);
setView('month');
