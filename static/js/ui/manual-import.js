let manualImagePreviewUrl = '';

function manualBody() {
    return {
        mode: valueOf('manualMode'),
        pasted_text: valueOf('manualText'),
        link: valueOf('manualLink'),
        title: valueOf('manualTitle'),
        start_time: valueOf('manualStart'),
        end_time: valueOf('manualEnd'),
        location: valueOf('manualLocation'),
        city: valueOf('manualCity'),
        organizer: valueOf('manualOrganizer'),
        description: valueOf('manualDesc'),
        registration_deadline: valueOf('manualDeadline'),
        registration_link: valueOf('manualRegLink'),
        tags: lines(valueOf('manualTags')),
        level: valueOf('manualLevel') || null
    };
}

async function saveManualEvent() {
    if (!valueOf('manualTitle') && !valueOf('manualStart')) {
        await analyzeManualEvent({ quiet: true });
    }
    const body = manualBody();
    const file = document.getElementById('manualImage')?.files?.[0];
    body.image_path = file ? file.name : '';
    const res = await fetch('/api/events/manual', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok || !data.success) return setLine('manualStatus', data.detail || '保存失败', 'err');
    setLine('manualStatus', '已保存到我的活动日历', 'ok');
    loadEvents();
}

async function analyzeManualEvent(options) {
    options = options || {};
    const btn = document.getElementById('manualAnalyzeBtn');
    const retryBtn = document.getElementById('manualRetryBtn');
    [btn, retryBtn].forEach(el => { if (el) el.disabled = true; });
    if (!options.quiet) setManualImportProgress('正在解析活动信息，图片可能需要稍等...');
    try {
        const file = document.getElementById('manualImage')?.files?.[0];
        const body = {
            mode: valueOf('manualMode') === 'manual' ? 'text' : valueOf('manualMode'),
            pasted_text: valueOf('manualText'),
            link: valueOf('manualLink'),
            title: valueOf('manualTitle')
        };
        let res;
        if (file) {
            const form = new FormData();
            Object.entries(body).forEach(([key, value]) => form.append(key, value || ''));
            form.append('image', file);
            res = await fetch('/api/events/manual/analyze-form', { method: 'POST', body: form });
        } else {
            res = await fetch('/api/events/manual/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        }
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.detail || '解析失败');
        const event = (data.data?.events || [])[0];
        if (!event) {
            setLine('manualStatus', '暂时没有识别到可保存的活动。可以补充正文，或直接在右侧填写后保存。', 'err');
            return null;
        }
        fillManualFormFromEvent(event);
        if (!options.quiet) setLine('manualStatus', '已识别并预填，可以检查后保存。', 'ok');
        return event;
    } catch (err) {
        if (!options.quiet) setLine('manualStatus', (err.message || '解析失败') + '。你仍然可以手动填写后保存。', 'err');
        return null;
    } finally {
        [btn, retryBtn].forEach(el => { if (el) el.disabled = false; });
    }
}

function fillManualFormFromEvent(event) {
    const set = (id, value) => {
        const el = document.getElementById(id);
        if (el && value !== undefined && value !== null && String(value).trim()) el.value = value;
    };
    set('manualTitle', event.title);
    set('manualStart', event.start_time || event.calendar_time);
    set('manualEnd', event.end_time);
    set('manualLocation', event.location);
    set('manualCity', event.city);
    set('manualOrganizer', event.organizer);
    set('manualDeadline', event.registration_deadline || event.signup_deadline);
    set('manualRegLink', event.registration_link || event.signup_url || event.source_url);
    set('manualDesc', event.description || event.reason);
    set('manualTags', (event.tags || []).join('，'));
    set('manualLevel', event.level || event.priority);
}

function setManualImportProgress(text) {
    setLine('manualStatus', text || '');
}

function clearManualImagePreview() {
    if (manualImagePreviewUrl) URL.revokeObjectURL(manualImagePreviewUrl);
    manualImagePreviewUrl = '';
    const preview = document.getElementById('manualImagePreview');
    const meta = document.getElementById('manualImageMeta');
    const label = document.getElementById('manualImageName');
    if (preview) {
        preview.removeAttribute('src');
        preview.classList.remove('is-visible');
    }
    if (meta) meta.textContent = 'JPG / PNG / WebP，建议小于 10MB。';
    if (label) label.textContent = '选择图片文件';
}

function updateManualImagePreview(file) {
    if (!file) {
        clearManualImagePreview();
        return;
    }
    if (manualImagePreviewUrl) URL.revokeObjectURL(manualImagePreviewUrl);
    manualImagePreviewUrl = URL.createObjectURL(file);
    const preview = document.getElementById('manualImagePreview');
    const meta = document.getElementById('manualImageMeta');
    const label = document.getElementById('manualImageName');
    if (preview) {
        preview.src = manualImagePreviewUrl;
        preview.classList.add('is-visible');
    }
    if (label) label.textContent = file.name;
    if (meta) {
        const size = file.size >= 1024 * 1024
            ? (file.size / 1024 / 1024).toFixed(1) + ' MB'
            : Math.max(1, Math.round(file.size / 1024)) + ' KB';
        meta.textContent = size + ' · ' + (file.type || '图片文件') + ' · 将用于 AI 视觉识别';
    }
}
