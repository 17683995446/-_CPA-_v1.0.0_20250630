// ===== 工具函数 =====
async function api(method, path, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API_BASE + path, opts);
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
