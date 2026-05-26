(function () {
    const MODAL_TEMPLATES = {};
    const modalMarkup = `<div class="modal-backdrop" id="addModal">
        <div class="modal">
            <div class="modal-head"><h2>添加活动</h2><button class="mini" data-action="close-modal" data-modal="addModal">关闭</button></div>
            <div class="modal-body">
                <section class="form-section">
                    <h3>快速导入</h3>
                    <div class="grid2">
                        <div class="field"><label>添加方式</label><select id="manualMode"><option value="manual">手动填写</option><option value="text">粘贴文本</option><option value="link">输入链接</option><option value="image">上传图片</option></select></div>
                        <div class="field"><label>链接</label><input id="manualLink" type="text" placeholder="https://..."></div>
                    </div>
                    <div class="field"><label>粘贴文本</label><textarea id="manualText" placeholder="粘贴活动通知、海报 OCR 或报名说明"></textarea></div>
                    <div class="field"><label>图片文件</label><input id="manualImage" type="file" accept="image/*"></div>
                </section>
                <section class="form-section">
                    <h3>基础信息</h3>
                    <div class="grid2">
                    <div class="field"><label>标题</label><input id="manualTitle" type="text"></div>
                    <div class="field"><label>标签</label><input id="manualTags" type="text" placeholder="AI，创业，讲座"></div>
                    </div>
                    <div class="field"><label>描述</label><textarea id="manualDesc"></textarea></div>
                </section>
                <section class="form-section">
                    <h3>时间地点</h3>
                    <div class="grid2">
                    <div class="field"><label>开始时间</label><input id="manualStart" type="text" placeholder="2026-05-22 19:00"></div>
                    <div class="field"><label>结束时间</label><input id="manualEnd" type="text"></div>
                    <div class="field"><label>地点</label><input id="manualLocation" type="text"></div>
                    <div class="field"><label>城市</label><input id="manualCity" type="text"></div>
                    </div>
                </section>
                <details class="form-section advanced-fields">
                    <summary>来源与 AI 推荐信息</summary>
                    <div class="grid2">
                    <div class="field"><label>主办方</label><input id="manualOrganizer" type="text"></div>
                    <div class="field"><label>报名截止</label><input id="manualDeadline" type="text"></div>
                    <div class="field"><label>报名链接</label><input id="manualRegLink" type="text"></div>
                    <div class="field"><label>等级</label><select id="manualLevel"><option value="">自动分级</option><option value="S">S 强相关</option><option value="A">A 值得关注</option><option value="B">B 一般相关</option><option value="C">C 低相关</option></select></div>
                    </div>
                </details>
                <div class="row-actions"><button class="primary" data-action="save-manual-event">保存到我的日历</button></div>
                <div class="status-line" id="manualStatus"></div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="extractModal">
        <div class="modal small">
            <div class="modal-head"><h2>导入公众号</h2><button class="mini" data-action="close-modal" data-modal="extractModal">关闭</button></div>
            <div class="modal-body">
                <div class="field"><label>公众号</label><input id="extractAccount" type="text" placeholder="公众号名称 / alias / fakeid"></div>
                <div class="grid2">
                    <div class="field"><label>开始日期</label><input id="extractStart" type="date"></div>
                    <div class="field"><label>结束日期</label><input id="extractEnd" type="date"></div>
                </div>
                <details class="form-section advanced-fields">
                    <summary>AI 导入选项</summary>
                    <div class="grid2">
                        <div class="field"><label>模型抽取</label><select id="extractLlm"><option value="true">开启</option><option value="false">关闭</option></select></div>
                        <div class="field"><label>海报识别</label><select id="extractVision"><option value="true">开启</option><option value="false">关闭</option></select></div>
                    </div>
                </details>
                <div class="row-actions"><button class="primary" id="extractBtn" data-action="run-account-range">批量提取活动</button></div>
                <div class="status-line" id="extractStatus"></div>
                <div class="progress-wrap" id="extractProgress">
                    <div class="progress-bar"><div class="progress-fill" id="extractProgressFill"></div></div>
                    <div class="progress-message" id="extractProgressMessage">等待开始</div>
                    <div class="progress-log" id="extractProgressLog"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="sourcesModal">
        <div class="modal">
            <div class="modal-head"><h2>信息源管理</h2><button class="mini" data-action="close-modal" data-modal="sourcesModal">关闭</button></div>
            <div class="modal-body">
                <div class="grid2">
                    <div class="field"><label>类型</label><select id="sourceType"><option value="wechat">公众号</option><option value="link">链接源</option></select></div>
                    <div class="field"><label>公众号名称 / 信息源名称</label><input id="sourceName" type="text" placeholder="例如：北大创新创业"></div>
                    <div class="field"><label>fakeid（可选）</label><input id="sourceFakeid" type="text" placeholder="不知道可以不填"></div>
                    <div class="field"><label>链接源 URL</label><input id="sourceUrl" type="text" placeholder="选择链接源时填写"></div>
                </div>
                <div class="row-actions"><button class="primary" data-action="add-source">添加信息源</button></div>
                <div class="status-line" id="sourceStatus"></div>
                <div class="source-list" id="sourceList"></div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="profileModal">
        <div class="modal">
            <div class="modal-head"><h2>个人信息</h2><button class="mini" data-action="close-modal" data-modal="profileModal">关闭</button></div>
            <div class="modal-body">
                <div class="grid2">
                    <div class="field"><label>身份</label><input id="profileIdentity" type="text"></div>
                    <div class="field"><label>职业</label><input id="profileProfession" type="text"></div>
                </div>
                <div class="field"><label>研究方向</label><input id="profileResearch" type="text"></div>
                <div class="field"><label>兴趣</label><textarea id="profileInterests" placeholder="每行一个"></textarea></div>
                <div class="field"><label>优先关键词</label><textarea id="profileKeywords" placeholder="每行一个"></textarea></div>
                <div class="field"><label>避免主题</label><textarea id="profileAvoid" placeholder="每行一个"></textarea></div>
                <div class="row-actions"><button class="primary" data-action="save-profile">保存画像</button></div>
                <div class="status-line" id="profileStatus"></div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="settingsModal">
        <div class="modal">
            <div class="modal-head"><h2>设置</h2><button class="mini" data-action="close-modal" data-modal="settingsModal">关闭</button></div>
            <div class="modal-body">
                <section class="form-section">
                    <h3>日历助手</h3>
                <div class="grid2">
                    <div class="field"><label>每日自动抓取</label><select id="settingEnabled"><option value="false">关闭</option><option value="true">开启</option></select></div>
                    <div class="field"><label>抓取时间</label><input id="settingTime" type="time"></div>
                    <div class="field"><label>日期范围</label><input id="settingLookbackDays" type="number" min="0" max="30" step="1" placeholder="0"><p>包含前 N 天到今天；0 表示只抓今天。</p></div>
                    <div class="field"><label>保留天数</label><input id="settingRetentionDays" type="number" min="1" max="365" step="1" placeholder="15"><p>未收藏活动超过这个天数会被删除，收藏永远保留。</p></div>
                    <div class="field"><label>自动导入日历</label><select id="settingImport"><option value="true">开启</option><option value="false">关闭</option></select></div>
                    <div class="field"><label>模型抽取</label><select id="settingLlm"><option value="true">开启</option><option value="false">关闭</option></select></div>
                    <div class="field"><label>海报识别</label><select id="settingVision"><option value="false">关闭</option><option value="true">开启</option></select></div>
                    <div class="field"><label>压缩长度</label><input id="settingMaxChars" type="number" min="1000" max="30000" step="500"></div>
                </div>
                </section>
                <details class="form-section advanced-fields">
                    <summary>高级抓取与防风控</summary>
                    <div class="grid2">
                        <div class="field"><label>正文抓取并发</label><input id="settingFetchConcurrency" type="number" min="1" max="5" step="1"><p>建议 1；代理池稳定时可调到 2。</p></div>
                        <div class="field"><label>单篇最小间隔（秒）</label><input id="settingFetchDelayMin" type="number" min="0" max="300" step="1"></div>
                        <div class="field"><label>单篇最大间隔（秒）</label><input id="settingFetchDelayMax" type="number" min="0" max="300" step="1"></div>
                        <div class="field"><label>公众号间隔（秒）</label><input id="settingAccountDelay" type="number" min="0" max="600" step="1"></div>
                        <div class="field"><label>每号最多抓正文</label><input id="settingMaxArticlesPerAccount" type="number" min="1" max="100" step="1"></div>
                        <div class="field"><label>验证后冷却（分钟）</label><input id="settingVerificationPause" type="number" min="0" max="720" step="5"></div>
                        <div class="field"><label>连续验证阈值</label><input id="settingVerificationThreshold" type="number" min="1" max="20" step="1"></div>
                        <div class="field"><label>必须使用代理池</label><select id="settingProxyRequired"><option value="false">否</option><option value="true">是</option></select><p>开启后未配置 PROXY_URLS 会停止抓正文。</p></div>
                    </div>
                    <div class="status-line" id="fetchSafetyStatus"></div>
                    <h3>最近抓取</h3>
                    <div id="runLog"></div>
                    <div class="row-actions utility-actions">
                        <button class="mini" data-action="open-fetch-records">查看完整记录</button>
                        <a class="btn mini" href="/history.html">历史记录</a>
                        <a class="btn mini" href="/admin.html">打开管理后台</a>
                    </div>
                </details>
                <div class="row-actions settings-actions">
                    <button class="primary" data-action="save-settings">保存设置</button>
                    <button data-action="run-automation-now">立即抓取所有关注源</button>
                    <button data-action="cleanup-old-events">清理过期活动</button>
                    <button data-action="cleanup-duplicate-events">清理重复活动</button>
                </div>
                <div class="status-line" id="settingsStatus"></div>
                <div class="progress-wrap" id="automationProgress">
                    <div class="progress-bar"><div class="progress-fill" id="automationProgressFill"></div></div>
                    <div class="progress-message" id="automationProgressMessage">等待开始</div>
                    <div class="progress-log" id="automationProgressLog"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="fetchRecordsModal">
        <div class="modal large">
            <div class="modal-head"><h2>抓取记录</h2><button class="mini" data-action="close-modal" data-modal="fetchRecordsModal">关闭</button></div>
            <div class="modal-body">
                <div class="records-toolbar">
                    <div>
                        <span class="eyebrow">Fetch History</span>
                        <p class="mode-description">查看每次抓取的时间、公众号、文章和抽取结果。</p>
                    </div>
                    <button class="mini" data-action="load-fetch-records">刷新</button>
                </div>
                <div class="status-line" id="fetchRecordsStatus"></div>
                <div class="fetch-records-list" id="fetchRecordsList"></div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop" id="dayModal">
        <div class="modal large">
            <div class="modal-head"><h2 id="dayModalTitle">当天活动</h2><button class="mini" data-action="close-modal" data-modal="dayModal">关闭</button></div>
            <div class="modal-body">
                <div id="dayModalBody" class="list-view"></div>
            </div>
        </div>
    </div>

    <div class="modal-backdrop drawer-backdrop event-detail-backdrop" id="editModal">
        <div class="modal drawer-panel event-detail-panel">
            <div class="modal-head detail-drawer-head">
                <div>
                    <span class="eyebrow">Event Detail</span>
                    <h2>活动详情</h2>
                </div>
                <button class="mini detail-close" data-action="close-modal" data-modal="editModal" aria-label="关闭活动详情">关闭</button>
            </div>
            <div class="modal-body event-detail-body">
                <input id="editId" type="hidden">
                <section class="detail-hero">
                    <div class="detail-title-block">
                        <label for="editTitle">活动标题</label>
                        <input id="editTitle" class="detail-title-input" type="text">
                    </div>
                    <div class="detail-summary" id="editSummary"></div>
                    <div class="status-line detail-duplicate" id="editDuplicateInfo"></div>
                </section>

                <section class="detail-section">
                    <div class="detail-section-head">
                        <h3>基础信息</h3>
                        <p>用于日历展示、筛选和导出。</p>
                    </div>
                    <div class="detail-form-grid">
                        <div class="field"><label for="editStart">开始时间</label><input id="editStart" type="text"></div>
                        <div class="field"><label for="editEnd">结束时间</label><input id="editEnd" type="text"></div>
                        <div class="field"><label for="editLocation">地点</label><input id="editLocation" type="text"></div>
                        <div class="field"><label for="editCity">城市</label><input id="editCity" type="text"></div>
                        <div class="field"><label for="editLevel">推荐等级</label><select id="editLevel"><option value="S">S 强相关</option><option value="A">A 值得关注</option><option value="B">B 一般相关</option><option value="C">C 低相关</option></select></div>
                        <div class="field"><label for="editStatus">活动状态</label><select id="editStatus"><option value="pending">待确认</option><option value="confirmed">已确认</option><option value="ignored">已忽略</option></select></div>
                        <div class="field"><label for="editDeadline">报名截止</label><input id="editDeadline" type="text"></div>
                        <div class="field"><label for="editRegLink">报名链接</label><input id="editRegLink" type="text"></div>
                        <div class="field detail-wide"><label for="editTags">标签</label><input id="editTags" type="text"><div class="field-help">多个标签可用逗号、顿号或换行分隔。</div></div>
                    </div>
                </section>

                <section class="detail-section">
                    <div class="detail-section-head">
                        <h3>AI 推荐信息</h3>
                        <p>帮助你判断这个活动是否值得参加。</p>
                    </div>
                    <div class="field"><label for="editReason">推荐理由</label><textarea id="editReason" class="detail-textarea compact"></textarea></div>
                    <div class="field"><label for="editDesc">活动描述</label><textarea id="editDesc" class="detail-textarea"></textarea></div>
                    <div class="field detail-source is-hidden" id="editSourceRow">
                        <label>原文链接</label>
                        <a class="btn detail-source-link" id="editSourceLink" href="#" target="_blank" rel="noopener">打开公众号原文</a>
                    </div>
                </section>

                <div class="detail-footer">
                    <div class="row-actions detail-actions"><button class="primary" data-action="save-edit">保存修改</button><button class="danger" id="deleteCurrentBtn" data-action="delete-current-event">彻底删除</button></div>
                    <div class="status-line detail-status" id="editStatusLine"></div>
                </div>
            </div>
        </div>
    </div>`;
    const parser = document.createElement('template');
    parser.innerHTML = modalMarkup;
    for (const modal of parser.content.querySelectorAll('.modal-backdrop[id]')) {
        MODAL_TEMPLATES[modal.id] = modal.outerHTML;
    }
    function ensureModal(id) {
        let modal = document.getElementById(id);
        if (!modal && MODAL_TEMPLATES[id]) {
            document.body.insertAdjacentHTML('beforeend', MODAL_TEMPLATES[id]);
            modal = document.getElementById(id);
        }
        return modal;
    }
    window.EventRadarModals = { ensureModal, templates: MODAL_TEMPLATES };
})();
