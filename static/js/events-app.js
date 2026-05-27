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
    modal.dataset.returnFocus = document.activeElement && document.activeElement !== document.body ? getOrAssignFocusId(document.activeElement) : '';
    modal.classList.add('is-open');
    document.body.classList.add('modal-open');
    setTimeout(() => {
        const panel = modal.querySelector('.modal');
        const focusTarget = firstFocusable(panel) || panel;
        focusTarget?.focus?.({ preventScroll: true });
    }, 0);
}
function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('is-open');
    if (!document.querySelector('.modal-backdrop.is-open')) document.body.classList.remove('modal-open');
    const returnId = modal.dataset.returnFocus;
    if (returnId) document.getElementById(returnId)?.focus?.({ preventScroll: true });
}
document.addEventListener('keydown', event => {
    const open = Array.from(document.querySelectorAll('.modal-backdrop.is-open')).pop();
    if (!open) return;
    if (event.key === 'Escape') {
        closeModal(open.id);
        return;
    }
    if (event.key === 'Tab') trapModalFocus(open, event);
});
function getOrAssignFocusId(el) {
    if (!el.id) el.id = 'focus-' + Math.random().toString(36).slice(2, 10);
    return el.id;
}
function trapModalFocus(modal, event) {
    const panel = modal.querySelector('.modal');
    const focusables = Array.from(panel.querySelectorAll([
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled]):not([type="hidden"])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])'
    ].join(','))).filter(el => el.offsetParent !== null || el === document.activeElement);
    if (!focusables.length) {
        event.preventDefault();
        panel.focus();
        return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
}
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
        case 'analyze-manual-event':
            analyzeManualEvent();
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
        case 'profile-fill-examples':
            fillProfileExamples();
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
        if (event.target && event.target.id === 'manualImage') {
            const file = event.target.files && event.target.files[0];
            updateManualImagePreview(file);
        }
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
