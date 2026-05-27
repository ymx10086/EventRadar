function sourceRow(source) {
    const subtitle = [
        source.source_type,
        source.alias || source.fakeid || source.url || '',
        source.auto_fetch ? '参与定时抓取' : '不参与定时抓取'
    ].filter(Boolean).join(' · ');
    return '<div class="source-row">' +
        '<div><strong>' + esc(source.name) + '</strong><p>' + esc(subtitle) + '</p></div>' +
        '<div class="row-actions">' +
        '<button class="mini" data-action="toggle-source-auto-fetch" data-source-id="' + esc(source.id) + '" data-auto-fetch="' + String(!source.auto_fetch) + '">' + esc(source.auto_fetch ? '暂停定时' : '加入定时') + '</button>' +
        '<button class="mini" data-action="delete-source" data-source-id="' + esc(source.id) + '">删除</button>' +
        '</div>' +
        '</div>';
}

async function loadSources() {
    const res = await fetch('/api/events/sources');
    const data = await res.json();
    const list = data.data.sources || [];
    setHTML('sourceList', list.map(sourceRow).join('') || '<div class="empty"><strong>暂无信息源</strong></div>');
}

async function toggleSourceAutoFetch(id, autoFetch) {
    const res = await fetch('/api/events/sources/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auto_fetch: !!autoFetch }) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('sourceStatus', data.detail || '更新失败', 'err');
    loadSources();
}

async function addSource() {
    const body = {
        source_type: valueOf('sourceType'),
        name: valueOf('sourceName'),
        fakeid: valueOf('sourceFakeid'),
        url: valueOf('sourceUrl')
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
