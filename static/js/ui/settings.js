async function loadSettings() {
    const data = await (await fetch('/api/events/settings')).json();
    const s = data.data.settings || {};
    const automation = data.data.automation || {};
    const safety = data.data.fetch_safety || automation.fetch_safety || {};
    setValue('settingEnabled', String(!!s.daily_fetch_enabled));
    setValue('settingTime', s.daily_fetch_time || '07:30');
    setValue('settingLookbackDays', s.daily_fetch_lookback_days || 0);
    setValue('settingRetentionDays', s.event_retention_days || 15);
    setValue('settingImport', String(s.auto_import_calendar !== false));
    setValue('settingLlm', String(s.use_llm !== false));
    setValue('settingVision', String(!!s.use_vision));
    setValue('settingMaxChars', s.max_chars || 9000);
    setValue('settingFetchConcurrency', s.wechat_fetch_concurrency || 1);
    setValue('settingFetchDelayMin', s.wechat_fetch_delay_min ?? 3);
    setValue('settingFetchDelayMax', s.wechat_fetch_delay_max ?? 8);
    setValue('settingAccountDelay', s.wechat_account_delay ?? 10);
    setValue('settingMaxArticlesPerAccount', s.wechat_max_articles_per_account || 20);
    setValue('settingVerificationPause', s.wechat_verification_pause_minutes ?? 30);
    setValue('settingVerificationThreshold', s.wechat_verification_stop_threshold || 2);
    setValue('settingProxyRequired', String(!!s.wechat_proxy_required));
    renderFetchSafetyStatus(safety);
    renderAutomationProgress(automation.progress || {});
}

async function saveSettings() {
    const body = {
        daily_fetch_enabled: valueOf('settingEnabled') === 'true',
        daily_fetch_time: valueOf('settingTime') || '07:30',
        daily_fetch_lookback_days: Number(valueOf('settingLookbackDays') || 0),
        event_retention_days: Number(valueOf('settingRetentionDays') || 15),
        auto_import_calendar: valueOf('settingImport') === 'true',
        use_llm: valueOf('settingLlm') === 'true',
        use_vision: valueOf('settingVision') === 'true',
        max_chars: Number(valueOf('settingMaxChars') || 9000),
        wechat_fetch_concurrency: Number(valueOf('settingFetchConcurrency') || 1),
        wechat_fetch_delay_min: Number(valueOf('settingFetchDelayMin') || 0),
        wechat_fetch_delay_max: Number(valueOf('settingFetchDelayMax') || 0),
        wechat_account_delay: Number(valueOf('settingAccountDelay') || 0),
        wechat_max_articles_per_account: Number(valueOf('settingMaxArticlesPerAccount') || 20),
        wechat_verification_pause_minutes: Number(valueOf('settingVerificationPause') || 0),
        wechat_verification_stop_threshold: Number(valueOf('settingVerificationThreshold') || 2),
        wechat_proxy_required: valueOf('settingProxyRequired') === 'true'
    };
    const res = await fetch('/api/events/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    setLine('settingsStatus', data.success ? '设置已保存' : (data.detail || '保存失败'), data.success ? 'ok' : 'err');
    if (data.success) renderFetchSafetyStatus((data.data && data.data.fetch_safety) || {});
}

async function runAutomationNow() {
    setLine('settingsStatus', '正在执行定时抓取流程...');
    resetAutomationProgress();
    const promise = fetch('/api/automation/run-events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ poll: true, lookback_days: Number(valueOf('settingLookbackDays') || 0) }) });
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
    const retentionDays = Number(valueOf('settingRetentionDays') || 15);
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
    setHTML('runLog', runs.map(r => {
        const result = r.result || {};
        const archive = result.archive || {};
        const events = result.events || {};
        return '<div class="log-row"><div><strong>' + esc(r.status === 'success' ? '抓取成功' : '抓取失败') + '</strong><p>' + esc(formatDateTime(r.started_at)) + ' · ' + esc(r.duration_seconds || 0) + 's · ' + esc(archive.article_count || events.article_count || 0) + ' 篇文章 · ' + esc(events.event_count || 0) + ' 个活动' + (r.error ? ' · ' + esc(r.error) : '') + '</p></div></div>';
    }).join('') || '<div class="empty"><strong>暂无抓取日志</strong></div>');
}
