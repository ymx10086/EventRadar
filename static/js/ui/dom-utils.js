function html(strings, ...values) {
    return strings.reduce((out, part, index) => out + part + (index < values.length ? esc(values[index]) : ''), '');
}

function raw(value) {
    return String(value || '');
}

function attrs(attributes) {
    return Object.entries(attributes || {})
        .filter(([, value]) => value !== false && value !== null && value !== undefined)
        .map(([key, value]) => value === true ? esc(key) : esc(key) + '="' + esc(value) + '"')
        .join(' ');
}

function setHTML(id, markup) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = markup || '';
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || '';
}

function firstFocusable(container) {
    if (!container) return null;
    return container.querySelector([
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled]):not([type="hidden"])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])'
    ].join(','));
}
