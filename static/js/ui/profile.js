async function loadProfile() {
    const data = await (await fetch('/api/events/profile')).json();
    const p = data.data.profile || {};
    setValue('profileDisplayName', p.display_name || '');
    setValue('profileIdentity', p.identity || '');
    setValue('profileProfession', p.profession || '');
    setValue('profileOrganization', p.organization || '');
    setValue('profileResearch', p.research_direction || '');
    setValue('profileGoals', p.goals || '');
    setValue('profileInterests', (p.interests || []).join('\n'));
    setValue('profileKeywords', (p.priority_keywords || []).join('\n'));
    setValue('profileEventTypes', (p.preferred_event_types || []).join('\n'));
    setValue('profileCities', (p.preferred_cities || []).join('\n'));
    setValue('profileFormats', (p.preferred_formats || []).join('\n'));
    setValue('profileLanguages', (p.language_preferences || []).join('\n'));
    setValue('profileAvailability', (p.availability || []).join('\n'));
    setValue('profileTimePreference', p.time_preference || '');
    setValue('profileMaxFee', p.max_fee || '');
    setValue('profileFocus', (p.recommendation_focus || []).join('\n'));
    setValue('profileAvoid', (p.avoid_topics || []).join('\n'));
    setValue('profileNotes', p.notes || '');
}

async function saveProfile() {
    const body = {
        display_name: valueOf('profileDisplayName'),
        identity: valueOf('profileIdentity'),
        profession: valueOf('profileProfession'),
        organization: valueOf('profileOrganization'),
        research_direction: valueOf('profileResearch'),
        goals: valueOf('profileGoals'),
        interests: lines(valueOf('profileInterests')),
        priority_keywords: lines(valueOf('profileKeywords')),
        preferred_event_types: lines(valueOf('profileEventTypes')),
        preferred_cities: lines(valueOf('profileCities')),
        preferred_formats: lines(valueOf('profileFormats')),
        language_preferences: lines(valueOf('profileLanguages')),
        availability: lines(valueOf('profileAvailability')),
        time_preference: valueOf('profileTimePreference'),
        max_fee: valueOf('profileMaxFee'),
        recommendation_focus: lines(valueOf('profileFocus')),
        avoid_topics: lines(valueOf('profileAvoid')),
        notes: valueOf('profileNotes')
    };
    const res = await fetch('/api/events/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    setLine('profileStatus', data.success ? '已保存偏好，后续活动会按新画像分级' : (data.detail || '保存失败'), data.success ? 'ok' : 'err');
}

function fillProfileExamples() {
    const examples = {
        profileIdentity: '学生 / 创业者',
        profileProfession: 'AI 产品与创业方向',
        profileOrganization: '高校 / 创业团队',
        profileResearch: 'AI Agent、创新创业、数字人文',
        profileGoals: '寻找高质量讲座、创业比赛、路演、黑客松和研究交流机会。',
        profileInterests: 'AI\n创新创业\n产品设计\n科研转化',
        profileKeywords: '人工智能\nAgent\n路演\n竞赛\n黑客松\n报名',
        profileEventTypes: '讲座\n论坛\n竞赛\n路演\n工作坊',
        profileCities: '北京\n上海\n线上',
        profileFormats: '线下\n线上\n混合',
        profileAvailability: '工作日晚上\n周末下午',
        profileLanguages: '中文\nEnglish',
        profileTimePreference: '优先晚上和周末',
        profileMaxFee: '免费或 100 元以内',
        profileFocus: '相关度\n报名截止\n地点明确\n高校/科研机构',
        profileAvoid: '纯广告\n无报名信息\n无明确时间',
        profileNotes: '优先推荐高校、科研机构、创业社区活动；不推荐泛泛的商业推广。'
    };
    Object.entries(examples).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el && !el.value.trim()) el.value = value;
    });
    setLine('profileStatus', '已填入示例，可按你的真实偏好继续调整。', 'ok');
}
