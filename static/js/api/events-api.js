async function requestDeleteEvents(ids) {
    const cleanIds = [...new Set((ids || []).filter(Boolean))];
    if (!cleanIds.length) throw new Error('这个活动缺少数据库 ID，无法彻底删除。请刷新列表后再试。');
    const res = cleanIds.length === 1
        ? await fetch('/api/events/' + encodeURIComponent(cleanIds[0]) + '?delete_files=true', { method: 'DELETE' })
        : await fetch('/api/events/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: cleanIds, delete_files: true })
        });
    let data = {};
    try {
        data = await res.json();
    } catch (err) {
        data = {};
    }
    if (!res.ok || !data.success) throw new Error(data.detail || '删除失败');
    return data.data || {};
}
