function openEdit(id) {
    const e = currentEvents.find(item => item.id === id || item._ui_key === id);
    if (!e) return;
    window.EventRadarModals?.ensureModal('editModal');
    setValue('editId', e.id || '');
    setValue('editTitle', e.title || '');
    setValue('editTags', (e.tags || []).join('，'));
    setValue('editStart', e.start_time || '');
    setValue('editEnd', e.end_time || '');
    setValue('editLocation', e.location || '');
    setValue('editCity', e.city || '');
    setValue('editLevel', e.level || e.priority || 'B');
    setValue('editStatus', e.status || 'pending');
    setValue('editDeadline', e.registration_deadline || e.signup_deadline || '');
    setValue('editRegLink', e.registration_link || e.signup_url || '');
    setValue('editReason', e.reason || '');
    setValue('editDesc', e.description || '');
    const summary = [
        e.calendar_time || e.start_time || '时间待定',
        e.location || '地点待定',
        e.source_name || e.account || '未知来源',
        levelText(e.level || e.priority || 'B'),
        statusText(e.status || 'pending')
    ];
    setHTML('editSummary', summary.map(item => html`<span>${item}</span>`).join(''));
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
    const id = valueOf('editId');
    const title = valueOf('editTitle');
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
    const id = valueOf('editId');
    const body = {
        title: valueOf('editTitle'),
        tags: lines(valueOf('editTags')),
        start_time: valueOf('editStart'),
        end_time: valueOf('editEnd'),
        location: valueOf('editLocation'),
        city: valueOf('editCity'),
        level: valueOf('editLevel'),
        status: valueOf('editStatus'),
        registration_deadline: valueOf('editDeadline'),
        registration_link: valueOf('editRegLink'),
        reason: valueOf('editReason'),
        description: valueOf('editDesc')
    };
    const res = await fetch('/api/events/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('editStatusLine', data.detail || '保存失败', 'err');
    setLine('editStatusLine', '已保存', 'ok');
    loadEvents();
}
