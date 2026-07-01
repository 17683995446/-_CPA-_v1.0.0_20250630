// ===== 页面导航 =====
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');

    // 移动端关闭侧边栏
    document.getElementById('sidebar').classList.remove('open');

    if (page === 'dashboard') loadDashboard();
    if (page === 'study') loadStudyPage();
    if (page === 'review') loadReviewPage();
    if (page === 'knowledge') loadKnowledgePage();
    if (page === 'viz') loadKnowledgeVizPage();
    if (page === 'journal') loadJournalPage();
    if (page === 'achievements') loadAchievementsPage();
}

// ===== 初始化 =====
window.addEventListener('DOMContentLoaded', () => {
    // 自动登录：检查 localStorage 中是否有已登录用户
    autoLogin();
});

async function autoLogin() {
    const savedId = localStorage.getItem('cpa_user_id');
    const savedUsername = localStorage.getItem('cpa_username');
    if (!savedId || !savedUsername) return;

    try {
        // 验证用户是否仍然存在
        const res = await fetch(`${API_BASE}/api/users/${savedId}`);
        if (!res.ok) {
            localStorage.removeItem('cpa_user_id');
            localStorage.removeItem('cpa_username');
            return;
        }
        const user = await res.json();
        if (!user || user.username !== savedUsername) {
            localStorage.removeItem('cpa_user_id');
            localStorage.removeItem('cpa_username');
            return;
        }
        currentUser = user;
        await loadUserData();
        showApp();
    } catch (e) {
        // 静默失败，留在登录页
        localStorage.removeItem('cpa_user_id');
        localStorage.removeItem('cpa_username');
    }
}

// ===== 键盘快捷键 =====
document.addEventListener('keydown', (e) => {
    // 仅在学习页答题时生效
    if (document.getElementById('study-question').style.display === 'none') return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // 数字键 1-4 选择选项
    if (e.key >= '1' && e.key <= '4') {
        const optIdx = parseInt(e.key) - 1;
        const options = document.querySelectorAll('.option-item');
        if (options[optIdx] && selectedOption === null) {
            selectOption(optIdx);
        }
    }
    // Enter 提交或下一题
    if (e.key === 'Enter') {
        const submitBtn = document.querySelector('#action-bar .btn-primary');
        if (submitBtn) submitBtn.click();
    }
});

// ===== 回到顶部按钮滚动监听 =====
document.querySelector('.main-content').addEventListener('scroll', function() {
    const btn = document.getElementById('back-to-top');
    if (this.scrollTop > 300) {
        btn.classList.add('show');
    } else {
        btn.classList.remove('show');
    }
});
