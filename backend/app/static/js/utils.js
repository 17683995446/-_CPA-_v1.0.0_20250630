// ===== 工具函数 =====

/**
 * HTML 转义，防止 XSS 攻击。
 * 所有动态文本在拼入 innerHTML 前必须调用此函数。
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * 安全拼接 HTML 模板字符串中的文本内容。
 * 用法: html`<p>${safeText(userInput)}</p>`
 */
function safeText(text) {
    return escapeHtml(text);
}

async function api(method, path, body = null, timeoutMs = 30000) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);

    // 使用 AbortController 实现超时控制
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    opts.signal = controller.signal;

    try {
        const res = await fetch(API_BASE + path, opts);
        clearTimeout(timeoutId);
        if (!res.ok) {
            let detail = '请求失败';
            try {
                const data = await res.json();
                detail = data.detail || detail;
            } catch (_) {}
            throw new Error(detail);
        }
        if (res.status === 204) return null;
        try {
            return await res.json();
        } catch (_) {
            return null;
        }
    } catch (e) {
        clearTimeout(timeoutId);
        if (e.name === 'AbortError') {
            throw new Error(`请求超时（${timeoutMs / 1000}s）`);
        }
        throw e;
    }
}

function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function showCelebration(title, text, emoji = '🎉') {
    document.getElementById('celebration-title').textContent = title;
    document.getElementById('celebration-text').textContent = text;
    document.getElementById('celebration-emoji').textContent = emoji;
    const el = document.getElementById('celebration');
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2500);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ===== 全局加载器辅助函数 =====
function showLoader() { document.getElementById('page-loader').classList.add('show'); }
function hideLoader() { document.getElementById('page-loader').classList.remove('show'); }
